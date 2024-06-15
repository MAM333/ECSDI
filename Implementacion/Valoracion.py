# -*- coding: utf-8 -*-
"""
Agent using Flask web services for receiving and registering product feedback
/comm is the entry point for agent communication
/Stop is the entry point to stop the agent

This agent periodically checks for received products, requests feedback, and registers it.
"""

import argparse
import datetime
import socket
import threading
from multiprocessing import Queue, Process
from random import randint
from time import sleep

from flask import Flask, request
from rdflib import Graph, Namespace, RDF, URIRef, Literal, XSD

from AgentUtil.ACLMessages import build_message, get_message_properties, registerAgent, send_message
from AgentUtil.Agent import Agent
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.OntologyNamespaces import ECSDI

__author__ = 'ECSDIstore'

# Define command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define if the server is open to the external network", action='store_true', default=False)
parser.add_argument('--port', type=int, help="Agent communication port")
parser.add_argument('--dhost', default=socket.gethostname(), help="Directory agent host")
parser.add_argument('--dport', type=int, help="Directory agent communication port")

# Logging
logger = config_logger(level=1)

# Parse command-line arguments
args = parser.parse_args()
port = args.port if args.port else 9040
hostname = '0.0.0.0' if args.open else socket.gethostname()
dport = args.dport if args.dport else 9000
dhostname = args.dhost if args.dhost else socket.gethostname()

# AGENT ATTRIBUTES ----------------------------------------------------------------------------------------

# Agent Namespace
agn = Namespace("http://www.agentes.org#")

# Message Count
mss_cnt = 0

# Agent Data
FeedbackAgent = Agent('FeedbackAgent',
                      agn.FeedbackAgent,
                      f'http://{hostname}:{port}/comm',
                      f'http://{hostname}:{port}/Stop')

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       f'http://{dhostname}:{dport}/Register',
                       f'http://{dhostname}:{dport}/Stop')

# Global triplestore graph
dsGraph = Graph()

# Queue
queue = Queue()

# Flask app
app = Flask(__name__)

# Incremental message counter
def getMessageCount():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

def register_message():
    """
    Sends a registration message to the directory service using a Request performative and a Register action
    """
    logger.info('Registering agent')
    gr = registerAgent(FeedbackAgent, DirectoryAgent, FeedbackAgent.uri, getMessageCount())
    return gr

@app.route("/comm")
def communication():
    """
    Communication Entrypoint
    """
    message = request.args['content']
    grafoEntrada = Graph()
    grafoEntrada.parse(data=message)
    messageProperties = get_message_properties(grafoEntrada)

    resultadoComunicacion = None

    if messageProperties is None:
        # Respond that the message was not understood
        resultadoComunicacion = build_message(Graph(), ACL['not-understood'], sender=FeedbackAgent.uri, msgcnt=getMessageCount())
    else:
        # Get the performative
        if messageProperties['performative'] != ACL.request:
            # If not a request, respond that the message was not understood
            resultadoComunicacion = build_message(Graph(), ACL['not-understood'], sender=DirectoryAgent.uri, msgcnt=getMessageCount())
        else:
            graph = Graph()
            seleccion = randint(0, 1)
            ontologyFile = open('../data/FiltrosDB' if seleccion == 1 else '../data/ComprasDB')
            graph.parse(ontologyFile, format='turtle')
            query =  """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                        PREFIX default: <http://www.owl-ontologies.com/ECSDIstore#>
                        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                        SELECT ?Producto ?Nombre ?Precio ?Descripcion
                        where {
                            ?Producto rdf:type default:Producto .
                            ?Producto default:Nombre ?Nombre .
                            ?Producto default:Precio ?Precio .
                            ?Producto default:Descripcion ?Descripcion .
                        }
                        GROUP BY ?Nombre ORDER BY DESC(COUNT(*)) LIMIT 10"""

            resultadoConsulta = graph.query(query)
            resultadoComunicacion = Graph()
            sujeto2 = ECSDI[f"RespuestaRecomendacion{getMessageCount()}"]
            for product in resultadoConsulta:
                product_nombre = product.Nombre
                product_precio = product.Precio
                product_descripcion = product.Descripcion
                sujeto = product.Producto
                resultadoComunicacion.add((sujeto, RDF.type, ECSDI.Producto))
                resultadoComunicacion.add((sujeto, ECSDI.Nombre, Literal(product_nombre, datatype=XSD.string)))
                resultadoComunicacion.add((sujeto, ECSDI.Precio, Literal(product_precio, datatype=XSD.float)))
                resultadoComunicacion.add((sujeto, ECSDI.Descripcion, Literal(product_descripcion, datatype=XSD.string)))
                resultadoComunicacion.add((sujeto2, ECSDI.Recomienda, URIRef(sujeto)))

    logger.info('Responding to the search request')
    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize, 200

@app.route("/Stop")
def stop():
    """
    Entrypoint to stop the agent
    """
    tidyUp()
    shutdown_server()
    return "Stopping server"

def comprobarYValorar():
    graph = Graph()
    ontologyFile = open('../data/EnviosDB')
    logger.info("Checking received products")
    graph.parse(ontologyFile, format='turtle')
    query = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                            PREFIX default: <http://www.owl-ontologies.com/ECSDIstore#>
                            PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
                            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                            SELECT DISTINCT ?Producto ?Nombre ?Precio ?Descripcion
                            where {
                                ?PeticionEnvio rdf:type default:PeticionEnvio .
                                ?PeticionEnvio default:Tarjeta ?Tarjeta .
                                ?PeticionEnvio default:De ?Compra .
                                ?PeticionEnvio default:FechaEntrega ?FechaEntrega .
                                ?Compra default:Contiene ?Producto .
                                ?Producto default:Nombre ?Nombre .
                                ?Producto default:Precio ?Precio .
                                ?Producto default:Descripcion ?Descripcion .
                            FILTER("""
    query += f""" ?FechaEntrega > '{(datetime.datetime.now() - datetime.timedelta(days=1)).date()}'^^xsd:date"""
    query += """)}"""

    resultadoConsulta = graph.query(query)
    grafoConsulta = Graph()
    logger.info("Making feedback request")
    accion = ECSDI[f"PeticionValoracion{getMessageCount()}"]
    grafoConsulta.add((accion, RDF.type, ECSDI.PeticionValoracion))
    graph2 = Graph()
    ontologyFile2 = open('../data/ValoracionesDB')
    graph2.parse(ontologyFile2, format='turtle')
    productList = [a for a, b, c in graph2]
    contador = 0
    for g in resultadoConsulta:
        if g.Producto not in productList:
            contador += 1
            grafoConsulta.add((g.Producto, RDF.type, ECSDI.Producto))
            grafoConsulta.add((accion, ECSDI.Valora, URIRef(g.Producto)))
    if contador != 0:
        # Get user info
        agente = getAgentInfo(agn.UserPersonalAgent, DirectoryAgent, FeedbackAgent, getMessageCount())
        # Get user feedback
        logger.info("Sending feedback request")
        resultadoComunicacion = send_message(build_message(grafoConsulta,
                                                           perf=ACL.request, sender=FeedbackAgent.uri,
                                                           receiver=agente.uri,
                                                           msgcnt=getMessageCount(), content=accion), agente.address)
        logger.info("Feedback received")
        for s, o, p in resultadoComunicacion:
            if o == ECSDI.Valoracion:
                graph2.add((s, o, p))
        logger.info("Registering feedback")
        graph2.serialize(destination='../data/ValoracionesDB', format='turtle')
        logger.info("Feedback registration completed")

def solicitarValoraciones():
    logger.info("Starting routine feedback request")
    thread = threading.Thread(target=comprobarYValorar)
    thread.start()
    logger.info("Routine feedback request completed")
    thread.join()
    sleep(120)
    solicitarValoraciones()

def tidyUp():
    """
    Actions to perform before stopping the agent
    """
    global queue
    queue.put(0)

def FeedbackBehaviour(queue):
    """
    Agent Behaviour in a concurrent thread
    :param queue: the queue
    """
    gr = register_message()

if __name__ == '__main__':
    # Run behaviours
    thread = threading.Thread(target=solicitarValoraciones)
    thread.start()
    ab1 = Process(target=FeedbackBehaviour, args=(queue,))
    ab1.start()

    # Run server
    app.run(host=hostname, port=port, debug=False)

    # Wait for behaviours to complete
    ab1.join()
    thread.join()
    print('The End')
