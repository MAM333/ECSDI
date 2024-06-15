# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier ###
"""

from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import XSD, Graph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF

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
AgenteVendedor = Agent('AgenteVendedor',
                  agn.AgenteVendedor,
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
    gr = registerAgent(AgenteVendedor, DirectoryAgent, AgenteVendedor.uri, getMessagesCount())
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
            Graph(), ACL['not-understood'], sender=AgenteVendedor.uri, msgcnt=getMessagesCount())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=AgenteVendedor.uri, msgcnt=getMessagesCount())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            content = messageProperties['content']
            accion = grafoEntrada.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.compra:
                #crea la factura que devuelve al cliente
                resultadoComunicacion = crearFactura(content, grafoEntrada)
    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize, 200

def crearFactura(content, grafoEntrada):
    logger.info('Registrar historial de compraaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
    #hauria de registrar la compra
    registrarCompra(grafoEntrada)
    
    logger.info('Triant el CLLLLLLLLLLLLLLLLL')
    #enviar los productos a un centro logístico, seleccionar el centro logístico
    
    #enviar la factura al cliente
    logger.info('Generant factura')
    
    all_products = Graph()
    all_products.parse('./database_producto.rdf', format='xml')
    
    grafoFactura = Graph()
    sujeto = ECSDI['Factura' + str(getMessagesCount())]
    grafoFactura.add((sujeto, RDF.type, ECSDI.Factura))
    
    # Extraer información de la petición de compra
   
    logger.info('precioooooooooooooooooo total')
    precioT = 0
    #afegir els productes i calcular el preu total 
    for product_id in grafoEntrada.objects(content, ECSDI.product_id):
        print('mi product id es.........', product_id)
        logger.info(product_id)
        idStr= str(product_id)
        precio = all_products.value(subject=ECSDI[idStr], predicate=ECSDI.price)
        print('el precioooooooooooooooo es', precio)
        precioT += float(precio)
        grafoFactura.add((sujeto, ECSDI.product_id, product_id))
        grafoFactura.add((sujeto, ECSDI.price, Literal(precio, datatype=XSD.float)))
    
    logger.info('precioTotal = ' + str(precioT))
    grafoFactura.add((sujeto, ECSDI.PrecioTotal, Literal(precioT, datatype=XSD.float)))
    logger.info('Factura generada')

    registrarCobroPendiente(grafoEntrada, int(precioT))
    return grafoFactura

def registrarCompra(grafoEntrada):
    logger.info('Registrando compra')
    grafoCompra = Graph()
    try:
        grafoCompra.parse('./database_compras.rdf', format='xml')
        logger.info('Cargando base de datos de compras')
    except Exception:
        logger.info('Creando base de datos de compras')
        
    logger.info('Registrant compra')
    global numCompra
    numCompra = len(list(grafoCompra.subjects(RDF.type, ECSDI.compra)))
    sujeto_compra = ECSDI[f"Compra{numCompra+1}"]
    grafoCompra.add((sujeto_compra, RDF.type, ECSDI.compra))
    grafoCompra.add((sujeto_compra, ECSDI.compra_id, Literal(f"Compra{numCompra+1}", datatype=XSD.string)))

    for s,p,o in grafoEntrada:
        if(p == ECSDI.client_id or p == ECSDI.fecha_envio or p == ECSDI.fecha_limite_devolucion or p == ECSDI.product_id or p == ECSDI.created_at):
            grafoCompra.add((sujeto_compra, p,o))
    
    grafoCompra.serialize(destination='./database_compras.rdf', format='xml')
    logger.info('Compra registrada')

def registrarCobroPendiente(grafoEntrada, precioT):
    logger.info('Registrando cobro pendiente')
    grafoCompra = Graph()
    try:
        grafoCompra.parse('./database_cobros_pendientes.rdf', format='xml')
        logger.info('Cargando base de datos de cobros pendientes')
    except Exception:
        logger.info('Creando base de datos de compras')
        
    logger.info('Registrant cobros')
    numCobro = len(list(grafoCompra.subjects(RDF.type, ECSDI.cobro_pendiente)))
    sujeto_cobro = ECSDI[f"Cobro{numCobro+1}"]
    grafoCompra.add((sujeto_cobro, RDF.type, ECSDI.cobro_pendiente))
    grafoCompra.add((sujeto_cobro, ECSDI.cobro_pendiente_id, Literal(f"Cobro{numCobro+1}", datatype=XSD.string)))
    grafoCompra.add((sujeto_cobro, ECSDI.compra_id, Literal(f"Compra{numCompra+1}", datatype=XSD.string)))
    grafoCompra.add((sujeto_cobro, ECSDI.precio_total, Literal(precioT)))

    for s,p,o in grafoEntrada:
        if(p == ECSDI.client_id):
            grafoCompra.add((sujeto_cobro, p,o))
    
    grafoCompra.serialize(destination='./database_cobros_pendientes.rdf', format='xml')
    logger.info('Cobro registrado')

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
    
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    
    '''
     global listaDeProductos
    logger.info('Iniciem la petición de compra de productos')
    listaDeIdProductosCompra = ['B0184OCGAP', 'B0184OCGUP']
    
    logger.info("checkboxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    numTarjeta = int(1234444)
    direccion = 'direccion'
    codigoPostal = 8080
    
    grafoCompra = Graph()
    
    logger.info("estamosssssssssssssssssssssssssssssssssssssss aqui")
    content = ECSDI['PeticionCompra' + '34']
    grafoCompra.add((content, RDF.type, ECSDI.PeticionCompra))
    grafoCompra.add((content, ECSDI.Tarjeta, Literal(numTarjeta, datatype=XSD.int)))
    grafoCompra.add((content, ECSDI.Direccion, Literal(direccion, datatype=XSD.string)))
    grafoCompra.add((content, ECSDI.CodigoPostal, Literal(codigoPostal, datatype=XSD.int)))
    for idProducto in listaDeIdProductosCompra:
        # Create a unique subject for each product
        product_subject = ECSDI[str(idProducto)]
        
        # Add a triple indicating that the purchase request includes this product
        grafoCompra.add((content, ECSDI.ProductoId, product_subject))


    crearFactura(None, grafoCompra)
    '''
    logger.info('The End')