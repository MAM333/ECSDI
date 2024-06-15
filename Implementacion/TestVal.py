//TestVal
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
    print(f"Compra: {compra_id}, Fecha envio: {fecha_envio}")
    
    # Get the current time
    current_time = datetime.now()

    # Parse fecha_envio and add 5 minutes
    if(fecha_envio == None):
        return "No hay fecha Envio"

    fecha_envio = datetime.strptime(productos_compras["fecha_envio"], "%Y-%m-%dT%H:%M:%S.%f")
    fecha_envio_plus_5 = fecha_envio + timedelta(minutes=5)
    to_rate = current_time > fecha_envio_plus_5
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
            'products_ids': productos_sin_valoracion,
        }
        
    return need_rating

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
        client_id = result['client_id']
        valoration_graph.add((URIRef(client_id), ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
        products_ids = result['products_ids']
        for product_id in products_ids:
            valoration_graph.add((URIRef(client_id),ECSDI.product_id, product_id))
    
    # Results will contain the return values of each call to recommending_for_client
    print(valoration_graph.serialize(format='xml'))

startValorations()