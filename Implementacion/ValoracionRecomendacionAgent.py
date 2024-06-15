import argparse
import logging

from datetime import datetime, timedelta, timezone

import socket
import sys
import threading
from multiprocessing import Queue, Process, Pool
import multiprocessing
import random 
from time import sleep

from flask import Flask, request, render_template, redirect, url_for
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD


from AgentUtil.ACL import ACL
from AgentUtil.ACLMessages import *
from AgentUtil.Agent import Agent
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
from AgentUtil.OntoNamespaces import ECSDI



from multiprocessing import Pool

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

mss_cnt = 0

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

def get_message_count():
    global mss_cnt
    if mss_cnt is None:
        mss_cnt = 0
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


def recommending_for_client(idClient):
    print("Recibida petición de recomendación")
    recommendation = []

    try:
        # Load data from database_compras.rdf
        database_compras = Graph()
        database_compras.parse("database_compras.rdf")

        # Load data from database_historialBusqueda.rdf
        database_historialBusqueda = Graph()
        database_historialBusqueda.parse("database_searchHistory.rdf")

        database_product = Graph()
        database_product = database_product.parse("database_producto.rdf")
    except Exception as e:
        print(f"Error parsing RDF files: {e}")
        return recommendation

    products_client = Graph()
    content = ECSDI['PossibleReomendation']
    
    for s, p, o in database_compras.triples((None, ECSDI.client_id, Literal(idClient, datatype=XSD.string))):
        compra_id = s
        for compra, pred, product_id in database_compras.triples((compra_id, ECSDI.product_id, None)):
            products_client.add((content, ECSDI.product_id, product_id))

    for s, p, o in database_historialBusqueda.triples((None, ECSDI.client_id, Literal(idClient, datatype=XSD.string))):
        search_id = s
        for search, pred, product_id in database_historialBusqueda.triples((search_id, ECSDI.product_id, None)):
            products_client.add((content, ECSDI.product_id, product_id))

    #print(products_client.serialize(format = 'xml'))
    
    products_list = []
    # Convert products to a list and randomly select up to 5 products if more than 5
    products_list = list(products_client.objects(subject=content, predicate=ECSDI.product_id))
    if len(products_list) > 5:
        products_list = random.sample(products_list, 5)

    recommendation = {
        'client_id': idClient,
        'products_ids': products_list,
    }

    return recommendation

def getIdClients():
    idClients = []
    try:
        # Load data from database_compras.rdf
        database_client= Graph()
        database_client.parse("database_compras.rdf")
    except Exception as e:
        print(f"Error parsing RDF files: {e}")
        return
    for s,p,o in database_client:
        if(p == ECSDI.client_id):
            client = str(o)
            idClients.append(client)
    return idClients

def startRecomendations():
    idClients = getIdClients()
    # Define the number of processes to be used (can be adjusted according to available CPU cores)
    num_processes = min(len(idClients), multiprocessing.cpu_count())

    # Create a pool of processes
    with Pool(num_processes) as pool:
        # Execute recommending_for_client function for each idClient in parallel
        results = pool.map(recommending_for_client, idClients)
    
    recommendation_graph = Graph()
    accion = ECSDI['ProductsRecommended' + str(get_message_count())]
    recommendation_graph.add((accion, RDF.type, ECSDI.ProductsRecommended))
    for result in results:
        client_id = result['client_id']
        recommendation_graph.add((accion, ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
        recommendation_graph.add((ECSDI[client_id], ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
        products_ids = result['products_ids']
        for product_id in products_ids:
            recommendation_graph.add((ECSDI[client_id],ECSDI.product_id, product_id))
    
    # Results will contain the return values of each call to recommending_for_client
    print(recommendation_graph.serialize(format='xml'))
    """
    Sends generated recommendations to AgentePersonal.
    """
    logger.info('Sending recommendations to AgentePersonal')
    agente_personal = getAgentInfo(agn.AgentePersonal, DirectoryAgent, ValoracionRecomendacionAgent, get_message_count())
    
    message = build_message(recommendation_graph, 
                               perf=ACL.request, 
                               sender=ValoracionRecomendacionAgent.uri, 
                               receiver=agente_personal.uri, 
                               msgcnt=get_message_count(), 
                               content=accion)
    send_message( message, agente_personal.address)
    return "Recomendation SENT"    



def comprobar_y_valorar(client_id):
    need_rating = []
    # Load purchase history
    graph_compras = Graph()
    try:
        with open('./database_compras.rdf') as ontology_file:
            print("Comprobando productos comprados")
            graph_compras.parse(ontology_file, format='xml')
    except FileNotFoundError:
        print("Database file for purchases not found.")
        return
    except Exception as e:
        print(f"Error loading purchase history: {str(e)}")
        return

    # SPARQL query to fetch the latest compra for the client
    print('ANTER QUERY')

    query = f"""
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?compra_id ?fecha_envio ?product_id
    WHERE {{
        ?compra rdf:type ns1:compra .
        ?compra ns1:client_id "{client_id}"^^<http://www.w3.org/2001/XMLSchema#string> . 
        ?compra ns1:compra_id ?compra_id .
        ?compra ns1:fecha_envio ?fecha_envio .
        ?compra ns1:product_id ?product_id .
    }}
    ORDER BY DESC(?fecha_envio)
    LIMIT 1
    """

    # Execute the simplified query
    qres = graph_compras.query(query)

    productos_compras = {
        "compra_id": None,
        "fecha_envio": None,
        "product_ids": []
    }

    for row in qres:
        productos_compras["compra_id"] = row.compra_id
        productos_compras["fecha_envio"] = str(row.fecha_envio)
        productos_compras["product_ids"].append(row.product_id)

    compra_id = productos_compras["compra_id"]
    productos_compras_ids = productos_compras["product_ids"]
    fecha_envio = productos_compras["fecha_envio"]
    print(f"Compra: {compra_id}, Lista productos: {productos_compras_ids}, Fecha envio: {fecha_envio}")
    
    # Get the current time
    current_time = datetime.now()

    # Parse fecha_envio and add 5 minutes
    if(fecha_envio == None):
        return "No hay fecha Envio"

    fecha_envio = datetime.strptime(productos_compras["fecha_envio"], "%Y-%m-%dT%H:%M:%S.%f")
    fecha_envio_plus_5 = fecha_envio + timedelta(minutes=5)
    to_rate = current_time > fecha_envio
    print('DDDDDDDDAAAAAAAAAAAAAAAAAAAAAAATTTTTTTTTTTTTTTTEEEEEEEEEEEEEEEESSSSSSS')
    print(current_time)
    print(fecha_envio_plus_5)

    if (not to_rate):
        return "No hay nuevos productos para valorar"
    
    # Load valuation history
    existing_valorations_database = False
    graph_valoraciones = Graph()
    try:
        graph_valoraciones.parse('./database_valoraciones.rdf', format='xml')
        print("comprobar_y_valorar Cargando base de datos de valoraciones")
        existing_valorations_database = True
    except FileNotFoundError:
        print("Base de datos de valoraciones no encontrada, creando una nueva")
        graph_valoraciones.bind('rdf', RDF)
        graph_valoraciones.bind('ecsdi', ECSDI)
    except Exception as e:
        print(f"Error loading valuation database: {str(e)}")
        return

    productos_sin_valoracion = []
    if to_rate:
        contenido = ECSDI['PeticionValoracion' ]
        grafoContenido = Graph()
        grafoContenido.add((contenido, RDF.type, ECSDI.PeticionValoracion))
        grafoContenido.add((contenido, ECSDI.compra_id, compra_id))
        grafoContenido.add((contenido, ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
        
        if existing_valorations_database:
            # SPARQL query to fetch valorations for the specific compra_id and product_ids
            valorations_query = f"""
            PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
            SELECT ?product_id
            WHERE {{
            ?valoracion rdf:type ns1:valoracion .
            ?valoracion ns1:compra_id "{compra_id}" .
            ?valoracion ns1:product_id ?product_id .
            }}
            """
            # Execute the query
            valorations_qres = graph_valoraciones.query(valorations_query)

            productos_valorados = {
                "compra_id": compra_id,
                "product_ids": []
            }

            for row in valorations_qres:
                productos_valorados["product_ids"].append(row.product_id)

            productos_valorados_ids = productos_valorados["product_ids"]
            productos_sin_valoracion = [pid for pid in productos_compras_ids if pid not in productos_valorados_ids]

        else:
            productos_sin_valoracion = productos_compras_ids
        
        need_rating = {
            'client_id': client_id,
            'compra_id': compra_id,
            'products_ids': productos_sin_valoracion,
        }
        logger.info(need_rating)
    return need_rating


def startValorations():
    idClients = getIdClients()
    # Define the number of processes to be used (can be adjusted according to available CPU cores)
    num_processes = min(len(idClients), multiprocessing.cpu_count())

    # Create a pool of processes
    with Pool(num_processes) as pool:
        # Execute recommending_for_client function for each idClient in parallel
        results = pool.map(comprobar_y_valorar, idClients)
    
    valoration_graph = Graph()
    accion = ECSDI['PeticionValoracion']
    valoration_graph.add((accion, RDF.type, ECSDI.PeticionValoracion))
    for result in results:
        if isinstance(result, dict) and 'client_id' in result and 'products_ids' in result:
            client_id = str(result['client_id'])
            compra_id = str(result['compra_id'])
            valoration_graph.add((URIRef(client_id), ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
            valoration_graph.add((URIRef(client_id), ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
            products_ids = result['products_ids']
            for product_id in products_ids:
                valoration_graph.add((URIRef(client_id),ECSDI.product_id, product_id))
        else:
            print(f"Unexpected result format: {result}")
    # Results will contain the return values of each call to recommending_for_client
    print(valoration_graph.serialize(format='xml'))

    logger.info('Sending Products to RATE to AgentePersonal')
    agente_personal = getAgentInfo(agn.AgentePersonal, DirectoryAgent, ValoracionRecomendacionAgent, get_message_count())
    
    message = build_message(valoration_graph, 
                            perf=ACL.request, 
                            sender=ValoracionRecomendacionAgent.uri, 
                            receiver=agente_personal.uri, 
                            msgcnt=get_message_count(), 
                            content=accion)
    send_message( message, agente_personal.address)
       
    return "Para Valorar SENT"


def registrarValoraciones(grafoEntrada):
    database_graph = Graph()
    database_graph.parse("database_valoraciones.rdf", format='xml')
    num = get_message_count()
    id = 'Valoracion'+ str(num)
    subject = ECSDI['Valoracion'+ str(num)]
    grafoA = Graph()
    grafoA.add((subject, RDF.type, ECSDI.valoracion))
    grafoA.add((subject, ECSDI.valoracion_id,Literal(id, datatype=XSD.string)))
    # Extract information from the input graph
    for s,p,o in grafoEntrada:
        valoracion = s
        if(p == ECSDI.valoracion_id or p == ECSDI.client_id or p == ECSDI.compra_id
           or p == ECSDI.product_id or p == ECSDI.rating or p == ECSDI.valoracion_texto):
            grafoA.add((subject,p,o))
        
    print(grafoA.serialize(format = 'xml'))
    # Add the new valoracion to the database graph
    database_graph += grafoA

    # Serialize and save the updated graph back to the database file
    database_graph.serialize(destination="database_valoraciones.rdf", format="xml")

    return "Registrado"



@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    #scheduler.shutdown()
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
                resultadoComunicacion = grafoOK

    return resultadoComunicacion.serialize(format='xml')               
    gr = build_message(Graph(), ACL['not-understood'], sender=ValoracionRecomendacionAgent.uri, receiver=None, msgcnt=0)
    return gr.serialize(format='xml'), 200

def solicitar_valoraciones():
    logger.info("Iniciando peticion rutinaria de valoraciones")
    threading.Thread(target=startValorations).start()
    sleep(60*7)
    solicitar_valoraciones()

def recomendar():
    logger.info("Iniciando peticion rutinaria de valoraciones")
    threading.Thread(target=startRecomendations).start()
    sleep(60*8)
    recomendar()



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
    threadVal = threading.Thread(target=solicitar_valoraciones)
    threadRecom = threading.Thread(target=recomendar)
    threadVal.start()
    threadRecom.start()
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Run server
    app.run(host=hostname, port=port)

    # Wait for threads to finish
    ab1.join()
    threadVal.join()
    threadRecom.join()
    logger.info('The End')    
