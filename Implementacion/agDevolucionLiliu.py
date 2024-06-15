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
from datetime import datetime, timedelta, timezone
import random 
from flask import Flask, request
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import FOAF, RDF,XSD

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import *
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
    port = 9004
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
DevolucionAgent = Agent('DevolucionAgent',
                  agn.DevolucionAgent,
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
    gr = registerAgent(DevolucionAgent, DirectoryAgent, DevolucionAgent.uri, getMessagesCount())
    return gr

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
            Graph(), ACL['not-understood'], sender=DevolucionAgent.uri, msgcnt=getMessagesCount())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=DevolucionAgent.uri, msgcnt=getMessagesCount())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            contenido = messageProperties['content']
            accion = grafoEntrada.value(subject=contenido, predicate=RDF.type)

            if accion == ECSDI.DevolverProducto:
                logger.info("Recibida peticion de Devolucion")                
                accepted = processDevolucion(grafoEntrada)
                if(accepted):
                    grafoOK = Graph()
                    mensajeOK = "Confirmado"
                    content = ECSDI['ok' + str(getMessagesCount())]
                    grafoOK.add((content, RDF.type, ECSDI.OK))
                    grafoOK.add((content, ECSDI.MensajeOK, Literal(mensajeOK, datatype=XSD.string)))
                    resultadoComunicacion = grafoOK
                else:
                    grafoRechazado = Graph()
                    mensajeRechazo = "Rechazado"
                    content = ECSDI['ok' + str(getMessagesCount())]
                    grafoRechazado.add((content, RDF.type, ECSDI.Rechazado))
                    grafoRechazado.add((content, ECSDI.MensajeRechazo, Literal(mensajeRechazo, datatype=XSD.string)))                    
                
                    resultadoComunicacion = grafoRechazado
                


    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize

def cobrarDevolucion(grafoEntrada):
    grafoContenido =Graph()
    accion = ECSDI['CobrarDevolucion'+ str(getMessagesCount())]
    grafoContenido.add((accion, RDF.type, ECSDI.CobrarDevolucion))
    for s, p, o in grafoEntrada.triples((None, ECSDI.precioTotal, None)):
        precio_total = o
        grafoContenido.add((accion, ECSDI.precioTotal, o))
    for s, p, o in grafoEntrada.triples((None, ECSDI.client_id, None)):
        client = o
        grafoContenido.add((accion, ECSDI.client_id, o))
    for s, p, o in grafoEntrada.triples((None, ECSDI.compra_id, None)):
        compra = o
        grafoContenido.add((accion, ECSDI.compra_id, o))
    for s, p, o in grafoEntrada.triples((None, ECSDI.devolucion_id, None)):
        devolucion = o
        grafoContenido.add((accion, ECSDI.devolucion_id, o))

    agente = getAgentInfo(agn.Tesorero, DirectoryAgent, DevolucionAgent, getMessagesCount())
    
    #Enviamos la peticion al agente buscador
    logger.info('Enviando peticion al cobro  Tesorero')

    message = build_message(
            grafoContenido, perf=ACL.request, sender=DevolucionAgent.uri, receiver=agente.uri, 
            msgcnt=getMessagesCount(), 
            content=accion)
    send_message(message, agente.address)



def processDevolucion(devolucionRequest):
    print(devolucionRequest.serialize(format='xml'))
    g_compras = Graph()
    g_compras.parse('database_compras.rdf', format='xml')
    
    accepted_graph = Graph()
    accepted_graph.bind("ns1", ECSDI)

    precio_total = 0.0
    compra_id = list(devolucionRequest.objects(None, ECSDI.compra_id))[0]

    for s, p, o in devolucionRequest.triples((None, ECSDI.precioTotal, None)):
        precio_total = o

    query = """
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?fecha_limite_devolucion
    WHERE {
        ?compra ns1:compra_id ?compra_id ;
                ns1:fecha_limite_devolucion ?fecha_limite_devolucion .
        FILTER (?compra_id = """ + f'"{compra_id}"' + """)
    }
    """

    qres = g_compras.query(query)
    b = False
    for row in qres:
        fecha_limite_devolucion = row.fecha_limite_devolucion.toPython()
        print(f"Fecha limite devolucion: {fecha_limite_devolucion}")
        if datetime.now() <= fecha_limite_devolucion:
            b = True
            num = getMessagesCount()
            subject = ECSDI['DevolucionAccepted' + str(num)]
            accepted_graph.add((subject, RDF.type, ECSDI.DevolucionAccepted))
            accepted_graph.add((subject,  ECSDI.compra_id, compra_id))
            accepted_graph.add((subject, ECSDI.precioTotal, precio_total))
            for s, p, o in devolucionRequest:
                if p == ECSDI.product_id:
                    product_id = str(o)
                    accepted_graph.add((subject, ECSDI.product_id, o))
                    id = 'DevolucionAccepted' + str(num)
                    accepted_graph.add((subject, ECSDI.devolucion_id, Literal(id, datatype = XSD.string)))
                    devolucion_uri = ECSDI[f'DevolucionAccepted{str(num)}/{product_id}']
                    accepted_graph.add((devolucion_uri, RDF.type, ECSDI.DevolucionAccepted))
                    accepted_graph.add((devolucion_uri, ECSDI.compra_id, compra_id))
                    accepted_graph.add((devolucion_uri, ECSDI.product_id, o))                    
                    # Add reason for each product
                    reason = list(devolucionRequest.objects(s, ECSDI.reason))
                    if reason:
                        accepted_graph.add((devolucion_uri, ECSDI.reason, reason[0]))
            print('accepted_graph')
            print(accepted_graph.serialize(format='xml'))
            registrarDevolucion(accepted_graph)
            cobrarDevolucion(accepted_graph)
    return b

def registrarDevolucion(grafoEntrada):
    logger.info("Añadiendo devolucion a la BD")
    grafoDevoluciones = Graph()
    
    try:
        grafoDevoluciones.parse('./database_devoluciones.rdf', format='xml')
        logger.info('Cargando base de datos de devoluciones')
    except FileNotFoundError:
        logger.info("Base de datos de devoluciones no encontrada, creando una nueva")
        grafoDevoluciones.bind('rdf', RDF)
        grafoDevoluciones.bind('ecsdi', ECSDI)
    except Exception as e:
        logger.error(f'Error loading database_devoluciones.rdf: {e}')
        return "Error loading database"

    grafoDevoluciones += grafoEntrada

    try:
        grafoDevoluciones.serialize(destination='./database_devoluciones.rdf', format="xml")
        logger.info("Base de datos de devoluciones actualizada")
    except Exception as e:
        logger.error(f'Error saving database_devoluciones.rdf: {e}')
        return "Error saving database"
    
    return "Guardado"

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
    logger.info('The End')