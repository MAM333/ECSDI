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


def comprobar_y_valorar():
    client_id = "02565434P"  # The specific tarjeta to filter by    
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

    # SPARQL query to fetch the latest compra for the client
    query = f"""
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?compra_id ?fecha_envio ?product_id
    WHERE {{
    ?compra rdf:type ns1:compra .
    ?compra ns1:client_id "{client_id}" .
    ?compra ns1:compra_id ?compra_id .
    ?compra ns1:fecha_envio ?fecha_envio .
    ?compra ns1:product_id ?product_id .
    }}
    ORDER BY DESC(?fecha_envio)
    LIMIT 1
    """

    # Execute the query
    qres = graph_compras.query(query)

    productos_compras = {
        "compra_id": None,
        "fecha_envio": None,
        "product_ids": []
    }

    for row in qres:
        productos_compras["compra_id"] = row.compra_id
        productos_compras["fecha_envio"] = row.fecha_envio
        productos_compras["product_ids"].append(row.product_id)

    compra_id = productos_compras["compra_id"]
    productos_compras_ids = productos_compras["product_ids"]
    # Get the current time
    current_time = datetime.datetime.utcnow()

    # Parse fecha_envio and add 5 minutes
    fecha_envio = datetime.datetime.strptime(productos_compras["fecha_envio"], "%Y-%m-%dT%H:%M:%SZ")
    fecha_envio_plus_5 = fecha_envio + datetime.timedelta(minutes=5)

    # Determine boolean to_rate
    to_rate = current_time > fecha_envio_plus_5
    
    # Load valuation history
    compare_existing_valorations = False
    graph_valoraciones = Graph()
    try:
        graph_valoraciones.parse('./database_valoraciones.rdf', format='xml')
        logger.info("comprobar_y_valorar Cargando base de datos de valoraciones")
        compare_existing_valorations = True
    except FileNotFoundError:
        logger.info("Base de datos de valoraciones no encontrada, creando una nueva")
        graph_valoraciones.bind('rdf', RDF)
        graph_valoraciones.bind('ecsdi', ECSDI)
    except Exception as e:
        logger.error(f"Error loading valuation database: {str(e)}")
        return

    productos_sin_valoracion = []
    if to_rate:
        contenido = ECSDI['PeticionValoracion'+ str(getMessageCount())]
        grafoContenido = Graph()
        grafoContenido.add((contenido, RDF.type, ECSDI.PeticionValoracion))
        grafoContenido.add((contenido, ECSDI.compra, compra_id))

        if compare_existing_valorations:
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
            products_to_rate = [pid for pid in productos_compras_ids if pid not in productos_valorados_ids]
            productos_sin_valoracion =  products_to_rate
            for product_id in productos_sin_valoracion:
                grafoContenido.add(contenido, ECSDI.product_id, product_id)
        else:
            productos_sin_valoracion = productos_compras_ids
            for product_id in productos_sin_valoracion:
                grafoContenido.add(contenido, ECSDI.product_id, product_id)


    return grafoContenido if productos_sin_valoracion else "No products to rate"

def valorar():
    global products_to_rate
    grafoEntrada = comprobar_y_valorar()
    if isinstance(grafoEntrada, Graph):
        print(grafoEntrada.serialize(format = 'xml'))
        logger.info("Productos para valorar preparados.")
        # Implement code to save in products_to_rate each product to rate of grafoEntrada
        products_to_rate = []
        for s, p, o in grafoEntrada:
            if p == ECSDI.product_id:
                products_to_rate.append(str(o))
        logger.info(f"Productos para valorar: {products_to_rate}")

    else:
        logger.info(grafoEntrada)
        products_to_rate = []
    
    return products_to_rate

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        product_id = request.form['product_id']
        valoracion = request.form['valoracion']
        # Handle form submission here
        logger.info("Recibida peticion de valoracion")
        grafoValoracion = Graph()
        content = ECSDI['RespuestaValoracion' + str(getMessageCount())]
        # content is uriref : http://ONTOLOGIA_ECSDI/RespuestaValoracion1
        grafoValoracion.add((content, RDF.type, ECSDI.RespuestaValoracion))
        grafoValoracion.add((content, ECSDI.Valoracion, Literal(int(valoracion), datatype=XSD.int)))
        grafoValoracion.add((content, ECSDI.ProductoId, URIRef(product_id)))
        
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
        for s, p, o in grafoValoracion:
            graph_valoraciones.add((s, p, o))
        
        # Save the updated RDF graph to the file
        try:
            with open('./database_valoraciones.rdf', 'wb') as rdf_file:
                rdf_file.write(graph_valoraciones.serialize(format='xml').encode('utf-8'))
                logger.info("Valoracion guardada correctamente en la base de datos")
        except Exception as e:
            logger.error(f"Error saving valuation to database: {str(e)}")
            return "Error saving valuation to database"
        
        return redirect(url_for('feedback'))
    
    products_to_rate = valorar()
    return render_template('feedback.html', products=products_to_rate)


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