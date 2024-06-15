# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier ###
"""

import sys
import os


# Agrega el directorio 'Entrega2.0' al PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname('Entrega2.0'), '..')))

from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import XSD, Graph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, registerAgent, send_message, get_message_properties
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

# Global dsgraph triplestore
dsgraph = Graph()

# Cola de comunicacion entre procesos
cola1 = Queue()

#funcion para incrementar el numero de mensajes
def getMessagesCount():
    global mss_cnt
    mss_cnt += 1
    return mss_cnt

def registrarBusqueda(grafoEntrada):
    logger.info('Registrando busqueda')
    grafoCompra = Graph()
    try:
        grafoCompra.parse('./database_historialBusquedatest.rdf', format='xml')
        logger.info('Cargando base de datos de busqueda')
    except Exception:
        logger.info('Creando base de datos de busqueda')
        
    logger.info('Registrant busqueda')
    sujeto_busqueda = ECSDI['Busqueda' + str(getMessagesCount())]
    grafoCompra.add((sujeto_busqueda, RDF.type, ECSDI.Busqueda))
    grafoCompra += grafoEntrada
    
    grafoCompra.serialize(destination='./database_historialBusquedatest.rdf', format='xml')
    logger.info('Compra registrada')
    
if __name__ == '__main__':
    
    contenido = ECSDI['BuscarProducto' + str(getMessagesCount())]
    grafoContenido = Graph()
    # subjecte = BuscarProducto string 
    # predicate = tipo de objeto
    # object = ECSDI.BuscarProducto
    grafoContenido.add((contenido, RDF.type, ECSDI.BuscarProducto))
    nombreProducto = ['Kindle']
    
    #si tenemos un nombre de producto lo añadimos al grafo
    if nombreProducto:
        print('Nombre del producto:', nombreProducto)
        nombreSujeto = ECSDI['RestriccionDeNombre' + str(getMessagesCount())]
        grafoContenido.add((nombreSujeto, RDF.type, ECSDI.RestriccionDeNombre))    
        grafoContenido.add((nombreSujeto, ECSDI.Nombre, Literal(nombreProducto, datatype=XSD.string)))
        grafoContenido.add((contenido, ECSDI.RestringidaPor, URIRef(nombreSujeto)))
        
    precioMin = 11
    precioMax = 200
    
     # Añadimos el rango de precios por el que buscaremos
    if precioMax or precioMin:
        print(precioMax)
        print(precioMin)
        precioSujeto = ECSDI['RestriccionDePrecio' + str(getMessagesCount())]
        grafoContenido.add((precioSujeto, RDF.type, ECSDI.RestriccionDePrecio))
        if precioMin:
            grafoContenido.add((precioSujeto, ECSDI.PrecioMinimo, Literal(precioMin)))
        if precioMax:
            grafoContenido.add((precioSujeto, ECSDI.PrecioMaximo, Literal(precioMax)))
        grafoContenido.add((contenido, ECSDI.RestringidaPor, URIRef(precioSujeto)))
        
    registrarBusqueda(grafoContenido)