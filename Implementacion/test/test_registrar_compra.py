from venv import logger
from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI
from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import XSD, Graph, Namespace, Literal
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
from AgenteBuscador import getMessagesCount

#lista_productos = []


def add_product(g, product_id, product_name, product_description, price):
    print(ECSDI[product_id])#crear un nou namesapace per cada producte 
    print(ECSDI.product)
    g.add((ECSDI[product_id], RDF.type, ECSDI.product))
    g.add((ECSDI[product_id], ECSDI.Nombre, Literal(product_name, datatype=XSD.string)))
    g.add((ECSDI[product_id], ECSDI.Id, Literal(product_id)))
    g.add((ECSDI[product_id], ECSDI.Descripcion, Literal(product_description, datatype=XSD.string)))
    g.add((ECSDI[product_id], ECSDI.Precio, Literal(price)))

def acteafegir():
    g = Graph()
    global lista_productos

    add_product(g, 'B0184OCGAK', 'Boli', 'Bon producte', 10)
    add_product(g, 'B0184OCGAG', 'Kindle', 'Bon producte', 50)
    add_product(g, 'B0184OCGAP', 'Kindle2', 'Bon producte', 100)
    add_product(g, 'B0184OCGUP', 'Kindle3', 'Bon producte', 20)
    
    lista_productos = []
    
    for s in g.subjects(RDF.type, ECSDI.product):
        producto = {}
    
        # Extraer las propiedades del producto
        producto['id'] = g.value(s, ECSDI.Id)
        producto['nombre'] = g.value(s, ECSDI.Nombre)
        producto['descripcion'] = g.value(s, ECSDI.Descripcion)
        producto['precio'] = g.value(s, ECSDI.Precio)
        
        # Añadir el diccionario del producto a la lista
        lista_productos.append(producto)


def registrarCompra(content, grafoEntrada):
    print('Registrando compra')
    grafoCompra = Graph()
    try:
        grafoCompra.parse('./database_historial.rdf', format='xml')
        logger.info('Cargando base de datos de compras')
    except Exception:
        logger.info('Creando base de datos de compras')
        
    print('Registrant compra')
    sujeto_compra = ECSDI['Compra' + '333333333333333333333333']
    grafoCompra.add((sujeto_compra, RDF.type, ECSDI.Compra))
    grafoCompra += grafoEntrada
    
    grafoCompra.serialize(destination='./database_historial.rdf', format='xml')
    print('Compra registrada')

if __name__ == '__main__':
    grafoCompra = Graph()
    numTarjeta = 123456789
    direccion = "Carrer de la Llibertat"
    codigoPostal = 29832
    content = ECSDI['PeticionCompra' + "333333333333333333"]
    grafoCompra.add((content, RDF.type, ECSDI.PeticionCompra))
    grafoCompra.add((content, ECSDI.Tarjeta, Literal(numTarjeta, datatype=XSD.int)))
    grafoCompra.add((content, ECSDI.Direccion, Literal(direccion, datatype=XSD.string)))
    grafoCompra.add((content, ECSDI.CodigoPostal, Literal(codigoPostal, datatype=XSD.int)))
    
    registrarCompra(content, grafoCompra)
    
