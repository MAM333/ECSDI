//TestRecom
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
    accion = ECSDI['ProductsRecommended']
    recommendation_graph.add((accion, RDF.type, ECSDI.ProductsRecommended))
    for result in results:
        client_id = result['client_id']
        recommendation_graph.add((URIRef(client_id), ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
        products_ids = result['products_ids']
        for product_id in products_ids:
            recommendation_graph.add((URIRef(client_id),ECSDI.product_id, product_id))
    
    # Results will contain the return values of each call to recommending_for_client
    print(recommendation_graph.serialize(format='xml'))


startRecomendations()