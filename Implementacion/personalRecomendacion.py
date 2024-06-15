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
AgentePersonal = Agent('AgentePersonal',
                       agn.AgentePersonal,
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
    gr = registerAgent(AgentePersonal, DirectoryAgent, AgentePersonal.uri, getMessageCount())
    return gr

def recomendar_producto():
    logger.info("Recibida peticion de recomendacion")

    # Cargar productos de la base de datos
    graph_productos = Graph()
    graph_productos.parse('./database_producto.rdf', format='xml')

    query = f"""
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?product ?Id ?Nombre ?Descripcion ?Precio
    WHERE {{
        ?product rdf:type ns1:product .
        ?product ns1:Id ?Id .
        ?product ns1:Nombre ?Nombre .
        ?product ns1:Descripcion ?Descripcion .
        ?product ns1:Precio ?Precio .
    }}
    ORDER BY ASC(?Precio)
    LIMIT 5
    """

    results = graph_productos.query(query)
    
    # Crear un nuevo grafo para almacenar los resultados
    grafo_resultado = Graph()
    sujeto_respuesta = ECSDI["Recomienda" + str(getMessageCount())]
    grafo_resultado.add((sujeto_respuesta,RDF.type, ECSDI.Recomienda))
    
    for result in results:
        product = result['product']
        product_id = result['Id']
        product_name = result['Nombre']
        product_description = result['Descripcion']
        price = result['Precio']

        grafo_resultado.add((product, RDF.type, ECSDI.Producto))
        grafo_resultado.add((product, ECSDI.Id, Literal(product_id, datatype=XSD.string)))
        grafo_resultado.add((product, ECSDI.Nombre, Literal(product_name, datatype=XSD.string)))
        grafo_resultado.add((product, ECSDI.Descripcion, Literal(product_description, datatype=XSD.string)))
        grafo_resultado.add((product, ECSDI.Precio, Literal(price, datatype=XSD.float)))

    return grafo_resultado


def pedirRecomendacion():
    grafoRecomendacion = recomendar_producto()
    logger.info("Recibido resultado de recomendacion")

    listaDeRecomendaciones = []

    # Extract products from grafoRecomendacion
    for product in grafoRecomendacion.subjects(RDF.type, ECSDI.Producto):
        product_id = grafoRecomendacion.value(product, ECSDI.Id)
        product_name = grafoRecomendacion.value(product, ECSDI.Nombre)
        product_description = grafoRecomendacion.value(product, ECSDI.Descripcion)
        product_price = grafoRecomendacion.value(product, ECSDI.Precio)

        recomendacion = {
            'id': str(product_id),
            'nombre': str(product_name),
            'descripcion': str(product_description),
            'precio': float(product_price)
        }

        listaDeRecomendaciones.append(recomendacion)
        
    return listaDeRecomendaciones

def recommending(idClient):
    logger.info("Recibida peticion de recomendacion")
    recommendation_graph = Graph()
    
    database_compras = Graph()
    database_compras.parse("database_compras.rdf")
    # Load data from database_historialBusqueda.rdf
    database_historialBusqueda = Graph()
    database_historialBusqueda.parse("database_historialBusqueda.rdf")

    # Query database_compras for products matching the client_id
    query_compras = database_compras.query(
        """
        SELECT ?compra_id ?product_id
        WHERE {
            ?compra rdf:type ECSDI:compra .
            ?compra ECSDI:client_id ?client_id .
            ?compra ECSDI:compra_id ?compra_id .
            ?compra ECSDI:product_id ?product_id .
            FILTER(?client_id = ?idClient)
        }
        """,
        initBindings={"idClient": Literal(idClient)}
    )

    # Query database_historialBusqueda for products matching the client_id
    query_historialBusqueda = database_historialBusqueda.query(
        """
        SELECT ?product_id
        WHERE {
            ?historial rdf:type ECSDI:historialBusqueda .
            ?historial ECSDI:client_id ?client_id .
            ?historial ECSDI:product_id ?product_id .
            FILTER(?client_id = ?idClient)
        }
        """,
        initBindings={"idClient": Literal(idClient)}
    )
        # Get the results of the queries
    compras_products = [(str(row[0]), str(row[1])) for row in query_compras]
    historialBusqueda_products = [str(row[0]) for row in query_historialBusqueda]

    # Randomly select three products from compras_products and two from historialBusqueda_products
    selected_compras = random.sample(compras_products, min(len(compras_products), 3))
    selected_historialBusqueda = random.sample(historialBusqueda_products, min(len(historialBusqueda_products), 2))
    database_product = Graph()
    database_product.parse("database_producto.rdf")

    accion = ECSDI['ProductsRecommended']
    recommendation_graph.add((accion, RDF.type, ECSDI.ProductsRecommended))
    # Add selected products to the recommendation graph
    for compra_id, product_id in selected_compras:
        recommendation_graph.add((accion, ECSDI.product_id, Literal(product_id, datatype=XSD.string)))


    for product_id in selected_historialBusqueda:
        recommendation_graph.add((accion, RDF.type, ECSDI.historialBusqueda))

    return recommendation_graph



@app.route("/recommend")
def recommend():
    recommendation_graph = recommending("02565434P")
    print(recommendation_graph.serialize(format="xml"))
    return 
#render_template('recommendation.html', products=pedirRecomendacion())

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