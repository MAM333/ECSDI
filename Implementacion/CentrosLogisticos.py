# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier ###
"""

from collections import defaultdict
from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import Graph, ConjunctiveGraph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, getAgentInfo, registerAgent, send_message, get_message_properties
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
import socket
from AgentUtil.OntoNamespaces import ECSDI

__author__ = 'javier'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor esta abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--verbose', help="Genera un log de la comunicacion del servidor web", action='store_true',
                    default=False)
parser.add_argument('--port', type=int,
                    help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', help="Host del agente de directorio")
parser.add_argument('--dport', type=int,
                    help="Puerto de comunicacion del agente de directorio")

def getMessageCount():
    global mss_cnt
    if mss_cnt is None:
        mss_cnt = 0
    mss_cnt += 1
    return mss_cnt

# Logging
logger = config_logger(level=1)

# parsing de los parametros de la linea de comandos
args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9001
else:
    port = args.port

if args.open:
    hostname = '0.0.0.0'
    hostaddr = gethostname()
else:
    hostaddr = hostname = socket.gethostname()

print('DS Hostname =', hostaddr)

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost

# Flask stuff
app = Flask(__name__)
if not args.verbose:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

# Configuration constants and variables
agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
mss_cnt = 0

# Datos del Agente
CentrosLogisticos = Agent('CentrosLogisticos',
                  agn.CentrosLogisticos,
                  'http://%s:%d/comm' % (hostaddr, port),
                  'http://%s:%d/Stop' % (hostaddr, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()

# Cola de comunicacion entre procesos
cola1 = Queue()

#funcion para incrementar el numero de mensajes
def getMessagesCount():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

#funcion para registrar el agente en el servicio de directorio
def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio

    :param gmess:
    :return:
    """

    logger.info('Nos registramos')
    gr = registerAgent(CentrosLogisticos, DirectoryAgent, CentrosLogisticos.uri, getMessagesCount())
    return gr

@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'


@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicacion del agente
    Simplemente retorna un objeto fijo que representa una
    respuesta a una busqueda de hotel

    Asumimos que se reciben siempre acciones que se refieren a lo que puede hacer
    el agente (buscar con ciertas restricciones, reservar)
    Las acciones se mandan siempre con un Request
    Prodriamos resolver las busquedas usando una performativa de Query-ref
    """
    global dsgraph
    global mss_cnt

    logger.info('Peticion de informacion recibida')

    # Extraemos el mensaje y creamos un grafo con el
    message = request.args['content']
    grafoEntrada = Graph()
    grafoEntrada.parse(data=message, format='xml')

    messageProperties = get_message_properties(grafoEntrada)
    resultadoComunicacion = None

    # Comprobamos que sea un mensaje FIPA ACL
    if messageProperties is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        resultadoComunicacion = build_message(
            Graph(), ACL['not-understood'], sender=CentrosLogisticos.uri, msgcnt=getMessagesCount())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=CentrosLogisticos.uri, msgcnt=getMessagesCount())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            content = messageProperties['content']
            accion = grafoEntrada.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.OrganizarLotes:
                resultadoComunicacion = organizarLotes(grafoEntrada)
            elif accion == ECSDI.SeleccionarLotes:
                resultadoComunicacion = seleccionarLotes(grafoEntrada)
            elif accion == ECSDI.EnviarProductos:
                resultadoComunicacion = enviarProductos(grafoEntrada)
    
    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize

def organizarLotes(grafoEntrada):

    cogerProductos()
    logger.info("Todo bien cogido")
    
    global grafoLotes
    grafoLotes = Graph()
    grafoLotes.parse('./database_lotes.rdf', format='xml')

    # Obtener el número de lotes ya almacenados para generar un nuevo lote_id
    num_lotes = len(list(grafoLotes.subjects(RDF.type, ECSDI.lote)))

    clientes = []
    # Iterar sobre los resultados para obtener los datos necesarios
    for row in results:
        client_id = row.client_id
        if client_id not in clientes:
            lote_uri = ECSDI[f"Lote{num_lotes+1}"]
            grafoLotes.add((lote_uri, RDF.type, ECSDI.lote))
            grafoLotes.add((lote_uri, ECSDI.lote_id, Literal(f"Lote{num_lotes + 1}", datatype=XSD.string)))
            grafoLotes.add((lote_uri, ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
            grafoLotes.add((lote_uri, ECSDI.enviado, Literal(False, datatype=XSD.boolean)))  # Inicializado como False

            precioTotal = 0
            for roww in results:
                if client_id == roww.client_id:
                    grafoLotes.add((lote_uri, ECSDI.product_id, Literal(roww.product_id, datatype=XSD.string)))
                    precioTotal = precioTotal + int(roww.precio_total)
            
            grafoLotes.add((lote_uri, ECSDI.precio_total, Literal(precioTotal)))
            clientes.append(client_id)
            num_lotes = num_lotes + 1

    grafoLotes.serialize('./database_lotes.rdf', format='xml')
    return grafoLotes

def cogerProductos():
    logger.info("Organizando Lotes")

    global grafoCompras
    grafoCompras = Graph()
    grafoCompras.parse('./database_compras.rdf', format='xml')

    global grafoPendiente
    grafoPendiente = Graph()
    grafoPendiente.parse('./database_cobros_pendientes.rdf', format='xml')
    
    logger.info("DB cargadas")

    dataset = ConjunctiveGraph()

    for s, p, o in grafoCompras:
        dataset.add((s, p, o, URIRef(ECSDI.compra)))
    for s, p, o in grafoPendiente:
        dataset.add((s, p, o, URIRef(ECSDI.cobro_pendiente)))

    logger.info("Info en dataset")

    dataset = ConjunctiveGraph()

    for s, p, o in grafoCompras:
        dataset.add((s, p, o, URIRef(ECSDI.Compra)))
    for s, p, o in grafoPendiente:
        dataset.add((s, p, o, URIRef(ECSDI.CobroPendiente)))

    logger.info("Info en dataset")

    query = f"""
    PREFIX ns1: <{ECSDI}>
    SELECT ?compra ?product_id ?client_id ?fecha_envio ?fecha_limite_devolucion ?cobro ?precio_total
    WHERE {{
      GRAPH <{ECSDI}Compra> {{
        ?compra ns1:compra_id ?compra_id .
        ?compra ns1:product_id ?product_id .
        ?compra ns1:client_id ?client_id .
        ?compra ns1:fecha_envio ?fecha_envio .
        ?compra ns1:fecha_limite_devolucion ?fecha_limite_devolucion .
      }}
      GRAPH <{ECSDI}CobroPendiente> {{
        ?cobro ns1:compra_id ?compra_id .
        ?cobro ns1:precio_total ?precio_total .
      }}
    }}
    """

    try:
        global results
        results = dataset.query(query)

        # Mostrar los resultados
        for row in results:
            logger.info(f"Compra: {row.compra}, Producto: {row.product_id}, Cliente: {row.client_id}, Fecha Envio: {row.fecha_envio}, Fecha Limite Devolucion: {row.fecha_limite_devolucion}, Cobro: {row.cobro}, Precio Total: {row.precio_total}")

    except Exception as e:
        logger.error(f"Error ejecutando la consulta: {e}")

    return results

def seleccionarLotes(grafoEntrada):

    #Seleccionamos todos los lotes pa enviar
    grafoCombinado = seleccionarTransportistas()
    
    return grafoCombinado

def seleccionarTransportistas():
    
    database_lotes = Graph()
    database_lotes.parse("./database_lotes.rdf")

    database_clientes = Graph()
    database_clientes.parse("./database_client.rdf")

    database_transportistas = Graph()
    database_transportistas.parse("./database_transportistas.rdf")

    global grafoTransportistasYLotes
    grafoTransportistasYLotes = Graph()

    global cobros
    cobros = []
    
    for lote in database_lotes.subjects(RDF.type, ECSDI.lote):
        lote_id = str(database_lotes.value(lote, ECSDI.lote_id))
        client_id = str(database_lotes.value(lote, ECSDI.client_id))
        precio_total = int(database_lotes.value(lote, ECSDI.precio_total))
        
        for transportista in database_transportistas.subjects(RDF.type, ECSDI.transportista):
            transportista_id = str(database_transportistas.value(transportista, ECSDI.transportista_id))
            localizacion_transportista = database_transportistas.value(transportista, ECSDI.localizacion)
            transportista_disponibilidad = bool(database_transportistas.value(transportista, ECSDI.disponibilidad))
            if transportista_disponibilidad:
                for cliente in database_clientes.subjects(RDF.type, ECSDI.client):
                    cliente_id = str(database_clientes.value(cliente, ECSDI.client_id))
                    
                    if cliente_id == client_id:  
                        localizacion_cliente = database_clientes.value(cliente, ECSDI.client_direction)

                        if localizacion_cliente == localizacion_transportista:
                            grafoTransportistasYLotes.add((URIRef(lote_id), ECSDI.lote_id, Literal(lote_id, datatype=XSD.string)))
                            grafoTransportistasYLotes.add((URIRef(lote_id), ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
                            grafoTransportistasYLotes.add((URIRef(lote_id), ECSDI.precio_total, Literal(precio_total)))
                            grafoTransportistasYLotes.add((URIRef(lote_id), ECSDI.transportista_id, Literal(transportista_id, datatype=XSD.string)))
                            precio = int(database_lotes.value(lote, ECSDI.precio_total))
                            cobros.append((int(precio), str(client_id)))

    logger.info(cobros)
    grafoAux = grafoTransportistasYLotes.serialize(format='xml')
    logger.info(grafoAux)
    return grafoTransportistasYLotes

def enviarProductos(grafoEntrada):

    
    content = ECSDI['CobrarPedidos' + str(getMessageCount())]

    grafoCobros = Graph()
    grafoCobros.add((content, RDF.type, ECSDI.CobrarPedidos))
    
    for cobro in cobros:
        grafoCobros.add((content, ECSDI.client_id, Literal(cobro[1], datatype=XSD.string)))
        grafoCobros.add((content, ECSDI.precio_total, Literal(cobro[0])))

    agente = getAgentInfo(agn.Tesorero, DirectoryAgent, CentrosLogisticos, getMessageCount())

    logger.info('Enviando peticion al Tesorero')

    mensaje=build_message(
            grafoCobros, perf=ACL.request, sender=CentrosLogisticos.uri, receiver=agente.uri, 
            msgcnt=getMessageCount(), 
            content=content)

    send_message(mensaje, agente.address)
    return grafoEntrada

def tidyup():
    """
    Acciones previas a parar el agente

    """
    global cola1
    cola1.put(0)


def agentbehavior1(cola):
    """
    Un comportamiento del agente

    :return:
    """
    # Registramos el agente
    gr = register_message()
    return gr


if __name__ == '__main__':
    '''
    directivasRestrictivas = {}
    #directivasRestrictivas['Nombre'] = 'Kindle'
    directivasRestrictivas['PrecioMax'] = 50
    directivasRestrictivas['PrecioMin'] = 10
    print('directivasRestrictivas', directivasRestrictivas)
    #directivasRestrictivas['PrecioMin'] = precioMin
    products = buscar_producto(**directivasRestrictivas)
    '''
    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    logger.info('The End')