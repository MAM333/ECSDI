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
from rdflib import Graph, Namespace, Literal
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

def buscar_producto(Nombre=None, PrecioMax=None, PrecioMin=None):
    print('Iniciando la búsqueda de productos')
    all_products = Graph()
    all_products.parse('./database_producto.rdf', format='xml')
    
    print("Total de tripletas cargadas:", len(all_products))  # Para verificar cuántas tripletas se han cargado
    # Construir las partes del filtro SPARQL dinámicamente
    filters = []
    if Nombre:
        filters.append(f'CONTAINS(LCASE(?Nombre), LCASE("{Nombre}"))')
    if PrecioMin is not None:
        filters.append(f'?Precio >= {float(PrecioMin)}')
    if PrecioMax is not None:
        filters.append(f'?Precio <= {float(PrecioMax)}')

    # Unir las condiciones del filtro con "&&" si existen filtros
    filter_clause = 'FILTER (' + ' && '.join(filters) + ')' if filters else ''
    
    # Formulamos la consulta SPARQL
    query = f"""
    PREFIX ns1: <{ECSDI}>
    SELECT ?product ?Id ?Nombre ?Descripcion ?Precio
    WHERE {{
        ?product rdf:type ns1:product ;
                 ns1:Nombre ?Nombre ;
                 ns1:Id ?Id ;
                 ns1:Descripcion ?Descripcion ;
                 ns1:Precio ?Precio .
        {filter_clause}
    }}
    """
    
    results = all_products.query(query)
    
    print("Resultados de la búsqueda:", len(results))
    
    
    # Crear un nuevo grafo para almacenar los resultados
    grafo_resultado = Graph()
    
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
        
    return grafo_resultado    

if __name__ == '__main__':
    
        
    print('-----------------------------------------')
    
    directivasRestrictivas = {}
    print('Sense ningun parametre')
    print('Imprimeix tots els productes')
    products = buscar_producto(**directivasRestrictivas)
    
    print('-----------------------------------------')
    
    print('Amb preu maxim')
    print('Imprimeix tots els productes inferior a aquest preu maxim de 50') 
    directivasRestrictivas['PrecioMax'] = 50
    products = buscar_producto(**directivasRestrictivas)
    
    print('-----------------------------------------')
    
    print('Amb preu maxim i minim')
    print('Imprimeix tots els productes inferior a aquest preu maxim de 50 i minim 10') 
    directivasRestrictivas['PrecioMin'] = 11
    products = buscar_producto(**directivasRestrictivas)
    
    print('-----------------------------------------')
    
    print('Amb nom Kindle')
    print('Imprimeix tots els productes inferior a aquest nom Kindle')
    directivasRestrictivas['PrecioMin'] = 10
    products = buscar_producto('Kindle')
    
    