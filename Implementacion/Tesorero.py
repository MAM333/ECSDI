# -*- coding: utf-8 -*-
"""
filename: SimpleInfoAgent

Antes de ejecutar hay que añadir la raiz del proyecto a la variable PYTHONPATH

Agente que se registra como agente de hoteles y espera peticiones

@author: javier ###
"""

from collections import defaultdict
from multiprocessing import Process, Queue
import logging
import argparse

from flask import Flask, request
from rdflib import Graph, ConjunctiveGraph, Namespace, Literal, URIRef
from rdflib.namespace import FOAF, RDF, XSD

from AgentUtil.ACL import ACL
from AgentUtil.FlaskServer import shutdown_server
from AgentUtil.ACLMessages import build_message, getAgentInfo, registerAgent, send_message, get_message_properties
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

def getMessageCount():
    global mss_cnt
    if mss_cnt is None:
        mss_cnt = 0
    mss_cnt += 1
    return mss_cnt

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
    dport = 9008
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
Tesorero = Agent('Tesorero',
                  agn.Tesorero,
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
    gr = registerAgent(Tesorero, DirectoryAgent, Tesorero.uri, getMessagesCount())
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
            Graph(), ACL['not-understood'], sender=Tesorero.uri, msgcnt=getMessagesCount())
    else:
        # Obtenemos la performativa
        perf = messageProperties['performative']

        if perf != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            resultadoComunicacion = build_message(
                Graph(), ACL['not-understood'], sender=Tesorero.uri, msgcnt=getMessagesCount())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia de acciones del agente
            # de registro
            content = messageProperties['content']
            accion = grafoEntrada.value(subject=content, predicate=RDF.type)

            if accion == ECSDI.CobrarPedidos:
                resultadoComunicacion = cobrar(grafoEntrada)
            elif accion == ECSDI.CobrarDevolucion:
                resultadoComunicacion = cobrarDev(grafoEntrada)
    
    serialize = resultadoComunicacion.serialize(format='xml')
    return serialize

def cobrar(cobros):

    logger.info("Cobramos")

    dinero = Graph()
    dinero.parse("./database_dinero.rdf")
    dinnero = 0
    for din in dinero.subjects(RDF.type, ECSDI.dinero):
        dinnero = int(dinero.value(din, ECSDI.dinero_valor))
        
        if dinnero:
            client_ids = []
            precios_totales = []

            # Extraer los valores del grafo
            for s, p, o in cobros:
                if p == ECSDI.client_id:
                    client_ids.append(str(o))
                elif p == ECSDI.precio_total:
                    precios_totales.append(int(o))

            # Combinar los valores en pares
            pares = list(zip(client_ids, precios_totales))
            
            logger.info(pares)
            database_clientes = Graph()
            database_clientes.parse("./database_client.rdf")
            for client_id, precio_total in pares:
                logger.info(client_id)
                encontrado = False
                for cliente in database_clientes.subjects(RDF.type, ECSDI.client):
                    if not encontrado:
                        clientee_id = str(database_clientes.value(cliente, ECSDI.client_id))
                        logger.info(clientee_id)
                        if clientee_id == client_id:
                            encontrado = True
                            cuenta_banc = str(database_clientes.value(cliente, ECSDI.cuenta_banc))
                            dinnero = dinnero + cobra(cuenta_banc, precio_total)
    
    nuevoDinero = Graph()
    nuevoDinero.add((ECSDI[id], RDF.type, ECSDI.dinero))
    nuevoDinero.add((ECSDI[id], ECSDI.dinero_valor, Literal(dinnero)))
    nuevoDinero.serialize('./database_dinero.rdf', format='xml')

    return cobros

def cobrarDev(grafoEntrada):
    grafoCobroDev = Graph()
    client = None
    accion = ECSDI['Cobro' + str(getMessagesCount())]
    grafoCobroDev.add((accion, RDF.type, ECSDI.Cobro))
    for s,p,o in grafoEntrada:
        if(p == ECSDI.precioTotal):
            precioTotal = float(o)
            grafoCobroDev.add((accion, p, o))
        elif (p == ECSDI.client_id):
            grafoCobroDev.add((accion, p, o))
            client = o

    precioTotal = int(precioTotal)
    database_clientes = Graph()
    database_clientes.parse("./database_client.rdf")     
    #Buscar cuenta bancaria cliente en database cliente
    found = False
    for s, p, o in database_clientes:
        # Check if the subject is a client and has the desired client_id
        if (s, RDF.type, ECSDI.client) in database_clientes and (s, ECSDI.client_id, Literal(client)) in database_clientes:
            # Get the cuenta_banc literal
            found = True
            cuenta_bancaria_client = database_clientes.value(s, ECSDI.cuenta_banc, None)
            cuenta_bancaria_client= str(cuenta_bancaria_client)
            break
    #buscar modificar dinero de cuenta bancaria
    if(found) :
        cobra(cuenta_bancaria_client, precioTotal)
    else:
        print("Client not found in the database.")                
    return grafoEntrada




def cobra(cuenta_banc, importe):

    grafoCobro = Graph()
    grafoCobro.add((ECSDI["Cobro"], RDF.type, ECSDI.cobro))

    content = ECSDI['Cobro' + str(getMessageCount())]
    grafoCobro.add((content, RDF.type, ECSDI.cobro))
    grafoCobro.add((content, ECSDI.importe, Literal(-importe)))
    grafoCobro.add((content, ECSDI.cuenta_banc, Literal(cuenta_banc, datatype=XSD.string)))

    agente = getAgentInfo(agn.AgenteBanco, DirectoryAgent, Tesorero, getMessageCount())

    logger.info('Enviando peticion al Banco')

    mensaje=build_message(
            grafoCobro, perf=ACL.request, sender=Tesorero.uri, receiver=agente.uri, 
            msgcnt=getMessageCount(), 
            content=content)

    msg = send_message(mensaje, agente.address)

    logger.info("Comunicacion con banco exitosa")

    return importe

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