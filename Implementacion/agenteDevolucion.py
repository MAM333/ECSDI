# -*- coding: utf-8 -*-
"""
filename: SimplePersonalAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Ejemplo de agente que busca en el directorio y llama al agente obtenido


Created on 09/02/2014 ###

@author: javier
"""

from multiprocessing import Process, Queue
import logging
import argparse
import random
from datetime import datetime, timedelta

from flask import Flask, request, render_template, redirect, url_for
from rdflib import XSD, Graph, Literal, Namespace, URIRef
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.DSO import DSO
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, getAgentInfo, registerAgent, send_message, get_message_properties
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.OntoNamespaces import ECSDI
from AgentUtil.Util import gethostname
import socket

__author__ = 'javier'

# Definimos los parametros de la linea de comandos
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
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
    port = 9002
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
    dhostname = gethostname()
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
AgenteDevolucion = Agent('AgenteDevolucion',
                       agn.AgenteDevolucion,
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


#Productos encontrados
listaDeProductos = []

#Productos para valorar
products_to_rate = []

def getMessageCount():
    global mss_cnt
    if mss_cnt is None:
        mss_cnt = 0
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
    gr = registerAgent(AgenteDevolucion, DirectoryAgent, AgenteDevolucion.uri, getMessageCount())
    return gr

def processDevolucion(DevolucionRequest):
    devolucion_graph = DevolucionRequest
    #devolucion_graph.parse(data=DevolucionRequest, format='xml')

    compras_graph = Graph()
    compras_graph.parse('database_compras.rdf', format='xml')

    devolucion_accepted_graph = Graph()
    respuesta_graph = Graph()
    content = ECSDI['RespuestaDevolucion' + str(getMessageCount())]
    respuesta_graph.add((content, RDF.type, ECSDI.RespuestaDevolucion))


    for s, _, _ in devolucion_graph.triples((None, RDF.type, ECSDI.DevolverProducto)):
        compra_id = str(list(devolucion_graph.objects(s, ECSDI.compra_id))[0])
        product_ids = [str(obj) for obj in devolucion_graph.objects(s, ECSDI.product_id)]
        
        for compra in compras_graph.subjects(RDF.type, ECSDI.compra):
            if str(list(compras_graph.objects(compra, ECSDI.compra_id))[0]) == compra_id:
                fecha_limite_devolucion = datetime.strptime(str(list(compras_graph.objects(compra, ECSDI.fecha_limite_devolucion))[0]), '%Y-%m-%dT%H:%M:%S.%f')

                if datetime.now() < fecha_limite_devolucion:
                    for product_id in product_ids:
                        devolucion_accepted_graph.add((s, RDF.type, ECSDI.DevolucionAceptada))
                        devolucion_accepted_graph.add((s, ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
                        devolucion_accepted_graph.add((s, ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
                    
                    registrarDevolucion(devolucion_accepted_graph)
                    mensaje = 'Devolucion en Proceso'
                    respuesta_graph.add((content, ECSDI.Ok, Literal(mensaje, datatype=XSD.string)))

                else:
                    mensaje = 'Denegado:Fuera de plaze de Devolucion'
                    respuesta_graph.add((content, ECSDI.NotOk, Literal(mensaje, datatype=XSD.string)))
    return respuesta_graph


def registrarDevolucion(grafoDevolucion):
    
    # Load the existing RDF data
    try:
        graph_devoluciones = Graph()
        graph_devoluciones.parse('./database_devoluciones.rdf', format='xml')
        logger.info("Base de datos de devoluciones cargada correctamente")
    except FileNotFoundError:
        logger.info("Base de datos de devoluciones no encontrada, creando una nueva")
        graph_devoluciones.bind('rdf', RDF)
        graph_devoluciones.bind('ecsdi', ECSDI)
    except Exception as e:
        logger.error(f"Error loading valuation database: {str(e)}")
        return "Error loading valuation database"

    # Add the new devolucion to the RDF graph
    for s, p, o in grafoDevolucion:
        graph_devoluciones.add((s, p, o))

    # Save the updated RDF graph to the file
    try:
        with open('./database_.rdf', 'wb') as rdf_file:
            rdf_file.write(graph_devoluciones.serialize(format='xml').encode('utf-8'))
            logger.info("Devolucion guardada correctamente en la base de datos")
    except Exception as e:
        logger.error(f"Error saving valuation to database: {str(e)}")
        return "Error saving valuation to database" 
    
@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicación del agente
    """
    global dsgraph
    global mss_cnt
    global products_to_rate

    logger.info('Peticion de comunicacion recibida')
    message = request.args['content']
    grafoEntrada = Graph()
    grafoEntrada.parse(data=message, format='xml')

    msgdic = get_message_properties(grafoEntrada)

    if msgdic is None:
        # Si no es un sobre valido respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevolucion.uri)
    else:
        # Extraemos la performativa del mensaje
        perf = msgdic['performative']

        # Si la performativa es un request
        if perf == ACL.request:
            # Averiguamos el tipo de contenido que tiene
            contenido = msgdic['content']
            accion = grafoEntrada.value(subject=contenido, predicate=RDF.type)
            logger.info(accion)
            if accion == ECSDI.DevolverProducto:
                logger.info("Recibida peticion de devolucion")      
                grafoRespuesta = processDevolucion(grafoEntrada)          
                
                logger.info("Despues procesar")
                serialize = grafoRespuesta.serialize(format='xml')
                logger.info("Preparando productos para valoración")
                return serialize, 200

    gr = build_message(Graph(), ACL['not-understood'], sender=AgenteDevolucion.uri, receiver=None, msgcnt=0)
    return gr.serialize(format='xml'), 200

@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


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
    #gr = register_message()
    #return gr
    pass


if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    
    logger.info('The End')