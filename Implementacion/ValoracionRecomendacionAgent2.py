"""
filename: ValoracionRecomendacionAgent.py
"""

import argparse
import logging

import datetime
import socket
import sys
import threading
from multiprocessing import Queue, Process
from random import randint
from time import sleep

from flask import Flask, request, render_template, redirect, url_for
from rdflib import Graph, Literal, URIRef, XSD
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.ACLMessages import *
from AgentUtil.Agent import Agent
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
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
    port = 9005
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

#trigger

# Datos del Agente
ValoracionRecomendacionAgent = Agent('ValoracionRecomendacionAgent',
                                     agn.ValoracionRecomendacionAgent,
                                     'http://%s:%d/comm' % (hostname, port),
                                     'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global dsgraph triplestore
dsgraph = Graph()

# Cola de comunicacion entre procesos
cola1 = Queue()

# Contador de mensajes
mss_cnt = 0

def get_message_count():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

# Funcion para registrar el agente en el servicio de directorio
def register_message():
    logger.info('Registrando el agente')
    gr = registerAgent(ValoracionRecomendacionAgent, DirectoryAgent, ValoracionRecomendacionAgent.uri, get_message_count())
    return gr

@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    return 'Nothing to see here'

def generate_recommendations():
    """
    Generates product recommendations based on purchase and search history.
    """
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
    sujeto_respuesta = ECSDI["Recomienda" + str(get_message_count())]
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
    
    send_recommendations(grafo_resultado)



def send_recommendations(recommendations):
    """
    Sends generated recommendations to AgentePersonal.
    """
    logger.info('Sending recommendations to AgentePersonal')
    agente_personal = getAgentInfo(agn.AgentePersonal, DirectoryAgent, ValoracionRecomendacionAgent, get_message_count())
    
    send_message(build_message(recommendations, 
                               perf=ACL.inform, 
                               sender=ValoracionRecomendacionAgent.uri, 
                               receiver=agente_personal.uri, 
                               msgcnt=get_message_count(), 
                               content=None), 
                 agente_personal.address)
    return "Recomendation SENT"





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
            Graph(), ACL['not-understood'], sender=ValoracionRecomendacionAgent.uri, msgcnt=get_message_count())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=ValoracionRecomendacionAgent.uri, msgcnt=get_message_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            content = messageProperties['content']
            accion = grafoEntrada.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.RespuestaValoracion:
                grafoOK = Graph()
                mensajeOK = "Confirmado"
                content = ECSDI['ok' + str(get_message_count())]
                grafoOK.add((content, RDF.type, ECSDI.OK))
                grafoOK.add((content, ECSDI.MensajeOK, Literal(mensajeOK, datatype=XSD.string)))
                logger.info("Recivido RespuestaValoracion")
                registrarValoraciones(grafoEntrada)
                serialize = grafoOK.serialize(format='xml')                
                return serialize, 200


            
    gr = build_message(Graph(), ACL['not-understood'], sender=ValoracionRecomendacionAgent.uri, receiver=None, msgcnt=0)
    return gr.serialize(format='xml'), 200

def registrarValoraciones(grafoEntrada):
    # Load the existing RDF data
    try:
        graph_valoraciones = Graph()
        graph_valoraciones.parse('./database_valoraciones.rdf', format='xml')
        logger.info("Base de datos de valoraciones cargada correctamente")
    except FileNotFoundError:
        logger.info("Base de datos de valoraciones no encontrada, creando una nueva")
        graph_valoraciones.bind('rdf', RDF)
        graph_valoraciones.bind('ecsdi', ECSDI)
    except Exception as e:
        logger.error(f"Error loading valuation database: {str(e)}")
        return "Error loading valuation database"

    # Add the new valoracion to the RDF graph
    for s, p, o in grafoEntrada:
        graph_valoraciones.add((s, p, o))
    
    # Save the updated RDF graph to the file
    try:
        with open('./database_valoraciones.rdf', 'wb') as rdf_file:
            rdf_file.write(graph_valoraciones.serialize(format='xml').encode('utf-8'))
            logger.info("Valoracion guardada correctamente en la base de datos")
    except Exception as e:
        logger.error(f"Error saving valuation to database: {str(e)}")
        return "Error saving valuation to database"    

def ConseguirProductosParaValorar():
    tarjeta = "1233445"  # The specific tarjeta to filter by    
    productos_compra_ids = set()
    productos_valoraciones_ids = set() 

    # Load purchase history
    graph_compras = Graph()
    try:
        with open('./database_historialcompra.rdf') as ontology_file:
            logger.info("Comprobando productos comprados")
            graph_compras.parse(ontology_file, format='xml')
    except FileNotFoundError:
        logger.error("Database file for purchases not found.")
        return
    except Exception as e:
        logger.error(f"Error loading purchase history: {str(e)}")
        return

    query = f"""
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT DISTINCT ?producto
    WHERE {{
        ?compra rdf:type ns1:PeticionCompra .
        ?compra ns1:Tarjeta "{tarjeta}"^^<http://www.w3.org/2001/XMLSchema#int> .
        ?compra ns1:ProductoId ?producto .
    }}
    """
    productos_compra = graph_compras.query(query)

    for result in productos_compra:
        productos_compra_ids.add(str(result[0]))

    # Load valuation history
    graph_valoraciones = Graph()
    try:
        graph_valoraciones.parse('./database_valoraciones.rdf', format='xml')
        logger.info("comprobar_y_valorar Cargando base de datos de valoraciones")
        query_valoraciones = """
        PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
        SELECT DISTINCT ?respuestaValoracion ?producto
        WHERE {
            ?respuestaValoracion rdf:type ns1:RespuestaValoracion .
            ?respuestaValoracion ns1:ProductoId ?producto .
        }
        """
        productos_valoraciones = graph_valoraciones.query(query_valoraciones)
        for result in productos_valoraciones:
            productos_valoraciones_ids.add(str(result[1]))

    except FileNotFoundError:
        logger.info("Base de datos de valoraciones no encontrada, creando una nueva")
        graph_valoraciones.bind('rdf', RDF)
        graph_valoraciones.bind('ecsdi', ECSDI)
    except Exception as e:
        logger.error(f"Error loading valuation database: {str(e)}")
        return

    # Find products in productos_compra_ids that are not in productos_valoraciones_ids
    productos_sin_valoracion = productos_compra_ids - productos_valoraciones_ids

    return productos_sin_valoracion

def comprobar_y_valorar():
    productos_sin_valoracion = ConseguirProductosParaValorar()
    contenido = ECSDI['PeticionValoracion'+ str(get_message_count())]
    grafoContenido = Graph()
    grafoContenido.add((contenido, RDF.type, ECSDI.PeticionValoracion))
    if productos_sin_valoracion:
        for producto_id in productos_sin_valoracion:
            logger.info(f"Solicitar valoración para el producto: {producto_id}")
            producto_uri = URIRef(producto_id)
            #grafoContenido.add((contenido, RDF.type, ECSDI.Producto))
            grafoContenido.add((contenido, ECSDI.ProductoId, producto_uri))
    else:
        grafoContenido.add((contenido, RDF.type, ECSDI.Vacio))
        vacio = "Vacio"
        grafoContenido.add((contenido, ECSDI.MensajeVacio, Literal(vacio, datatype=XSD.string)))
    
    resultadoComunicacion = None
    agente_personal = getAgentInfo(agn.AgentePersonal, DirectoryAgent, ValoracionRecomendacionAgent, get_message_count())
    logger.info("Enviando peticion de valoracion")
    try:
        mensaje=build_message(
            grafoContenido, perf=ACL.request, sender=ValoracionRecomendacionAgent.uri, 
            receiver=agente_personal.uri, msgcnt=get_message_count(), content=contenido)
        logger.info("mensage hecho")
        logger.info(mensaje)
        resultadoComunicacion = send_message(mensaje, agente_personal.address)
        logger.info("DESPUES send_message PETICIONVALORACION")
        return

    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        return
    

def solicitar_valoraciones():
    logger.info("Iniciando peticion rutinaria de valoraciones")
    threading.Thread(target=comprobar_y_valorar).start()
    sleep(120)
    solicitar_valoraciones()

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
    # Start behavior thread
    thread = threading.Thread(target=solicitar_valoraciones)
    thread.start()
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Run server
    app.run(host=hostname, port=port)

    # Wait for threads to finish
    ab1.join()
    thread.join()
    logger.info('The End')    
