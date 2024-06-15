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
from rdflib import Graph, Namespace, Literal, XSD
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, registerAgent, send_message, get_message_properties
from AgentUtil.Agent import Agent
from AgentUtil.Logging import config_logger
from AgentUtil.DSO import DSO
from AgentUtil.Util import gethostname
import socket
from datetime import datetime
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
AgenteBuscador = Agent('AgenteBuscador',
                  agn.AgenteBuscador,
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
    gr = registerAgent(AgenteBuscador, DirectoryAgent, AgenteBuscador.uri, getMessagesCount())
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
            Graph(), ACL['not-understood'], sender=AgenteBuscador.uri, msgcnt=getMessagesCount())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=AgenteBuscador.uri, msgcnt=getMessagesCount())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            content = messageProperties['content']
            accion = grafoEntrada.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.Search:
                resultadoComunicacion = buscarProducto(content, grafoEntrada)
    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize, 200

def buscarProducto(content, grafoEntrada):
    # Extraemos las restricciones de busqueda que se nos pasan y creamos un contenedor de las restriciones
    # para su posterior procesamiento
    logger.info('registrando busqueda')
    #registrarBusqueda(grafoEntrada)
    logger.info('registro de busqueda completado')

    global client_id
    for cl in grafoEntrada.objects(content, ECSDI.client_id):
        logger.info(cl)
        client_id = cl
    
    logger.info("Recibida peticion de busqueda")
    restricciones = grafoEntrada.objects(content, ECSDI.RestringidaPor)
    directivasRestrictivas = {}
    for restriccion in restricciones:
        if grafoEntrada.value(subject=restriccion, predicate=RDF.type) == ECSDI.RestriccionDeNombre:
            nombre = grafoEntrada.value(subject=restriccion, predicate=ECSDI.Nombre)
            directivasRestrictivas['Nombre'] = nombre
            print("NOMBREEEEEEEEEEEEE = ", nombre)
        elif grafoEntrada.value(subject=restriccion, predicate=RDF.type) == ECSDI.RestriccionDePrecio:
            precioMax = grafoEntrada.value(subject=restriccion, predicate=ECSDI.PrecioMaximo)
            precioMin = grafoEntrada.value(subject=restriccion, predicate=ECSDI.PrecioMinimo)
            directivasRestrictivas['PrecioMax'] = precioMax
            directivasRestrictivas['PrecioMin'] = precioMin
    # Llamamos a una funcion que nos retorna un grafo con la información acorde al filtro establecido por el usuario
    resultadoComunicacion = buscar_producto(**directivasRestrictivas)
    return resultadoComunicacion

def buscar_producto(Nombre=None, PrecioMax=None, PrecioMin=None):
    logger.info('Iniciando la búsqueda de productos')
    all_products = Graph()
    all_products.parse('./database_producto.rdf', format='xml')
    
    print("Total de tripletas cargadas:", len(all_products))  # Para verificar cuántas tripletas se han cargado
    # Construir las partes del filtro SPARQL dinámicamente
    filters = []
    if Nombre:
        filters.append(f'CONTAINS(LCASE(?product_name), LCASE("{Nombre}"))')
    if PrecioMin is not None:
        filters.append(f'?price >= {float(PrecioMin)}')
    if PrecioMax is not None:
        filters.append(f'?price <= {float(PrecioMax)}')

    # Unir las condiciones del filtro con "&&" si existen filtros
    filter_clause = 'FILTER (' + ' && '.join(filters) + ')' if filters else ''
    
    # Formulamos la consulta SPARQL
    query = f"""
    PREFIX ns1: <{ECSDI}>
    SELECT ?product ?product_id ?product_name ?product_description ?price
    WHERE {{
        ?product rdf:type ns1:product ;
                 ns1:product_name ?product_name ;
                 ns1:product_id ?product_id ;
                 ns1:product_description ?product_description ;
                 ns1:price ?price .
        {filter_clause}
    }}
    """
    
    results = all_products.query(query)

    #registrarBusqueda(results)

    print("Resultados de la búsqueda:", len(results))
    
    
    # Crear un nuevo grafo para almacenar los resultados
    grafo_resultado = Graph()
    productos = []
    
    for result in results:
        product = result[0]
        product_id = result[1]
        product_name = result[2]
        product_description = result[3]
        price = result[4]
        
        print("Producto encontrado:", product_id, product_name, product_description, price)
        # Agregar tripletas al grafo de resultados
        grafo_resultado.add((product, RDF.type, ECSDI.product))
        grafo_resultado.add((product, ECSDI.Id, Literal(product_id)))
        grafo_resultado.add((product, ECSDI.Nombre, Literal(product_name)))
        grafo_resultado.add((product, ECSDI.Descripcion, Literal(product_description)))
        grafo_resultado.add((product, ECSDI.Precio, Literal(price)))

        productos.append(product_id)

    registrarBusqueda(productos)
        
    return grafo_resultado

def registrarBusqueda(productos_id):

    logger.info("Registrando Busqueda")
    grafoHistorial = Graph()
    grafoHistorial.parse('./database_searchHistory.rdf', format='xml')

    numSearch = len(list(grafoHistorial.subjects(RDF.type, ECSDI.Search)))
    searchUri = ECSDI[f"Search{numSearch+1}"]
    grafoHistorial.add((searchUri, RDF.type, ECSDI.Search))
    grafoHistorial.add((searchUri, ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
    grafoHistorial.add((searchUri, ECSDI.search_id, Literal(f"Search{numSearch+1}", datatype=XSD.string)))
    for idProducto in productos_id:
        grafoHistorial.add((searchUri, ECSDI.product_id, Literal(idProducto, datatype=XSD.string)))
    grafoHistorial.add((searchUri, ECSDI.createdAt, Literal(datetime.now(), datatype=XSD.dateTime)))

    grafoHistorial.serialize('database_searchHistory.rdf', format='xml')

    logger.info("Busqueda registrada")

    return

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