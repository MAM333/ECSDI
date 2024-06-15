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
compra_to_rate = []
client_to_rate = []
#Productos recomendados
listaDeRecomendaciones = {}

idCliente = '02565434P'
listCompras = {}
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


def directory_search_message(type):
    """
    Busca en el servicio de registro mandando un
    mensaje de request con una accion Seach del servicio de directorio

    Podria ser mas adecuado mandar un query-ref y una descripcion de registo
    con variables

    :param type:
    :return:
    """
    global mss_cnt
    logger.info('Buscamos en el servicio de registro')

    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[AgentePersonal.name + '-search']
    gmess.add((reg_obj, RDF.type, DSO.Search))
    gmess.add((reg_obj, DSO.AgentType, type))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgentePersonal.uri,
                        receiver=DirectoryAgent.uri,
                        content=reg_obj,
                        msgcnt=mss_cnt)
    gr = send_message(msg, DirectoryAgent.address)
    mss_cnt += 1
    logger.info('Recibimos informacion del agente')

    return gr


def infoagent_search_message(addr, ragn_uri):
    """
    Envia una accion a un agente de informacion
    """
    global mss_cnt
    logger.info('Hacemos una peticion al servicio de informacion')

    gmess = Graph()

    # Supuesta ontologia de acciones de agentes de informacion
    IAA = Namespace('IAActions')

    gmess.bind('foaf', FOAF)
    gmess.bind('iaa', IAA)
    reg_obj = agn[AgentePersonal.name + '-info-search']
    gmess.add((reg_obj, RDF.type, IAA.Search))

    msg = build_message(gmess, perf=ACL.request,
                        sender=AgentePersonal.uri,
                        receiver=ragn_uri,
                        msgcnt=mss_cnt)
    gr = send_message(msg, addr)
    mss_cnt += 1
    logger.info('Recibimos respuesta a la peticion al servicio de informacion')

    return gr


@app.route("/iface", methods=['GET', 'POST'])
def browser_iface():
    """
    Permite la comunicacion con el agente via un navegador
    via un formulario
    """
    if request.method == 'GET':
        return render_template('iface.html')
    else:
        user = request.form['username']
        mess = request.form['message']
        return render_template('riface.html', user=user, mess=mess)

def get_product_info(product_id):
    grafoProductos = Graph()
    grafoProductos.parse('./database_producto.rdf', format='xml')
    for s, p, o in grafoProductos:
        if s == ECSDI[product_id]:
            product_name = grafoProductos.value(s, ECSDI.product_name)
            product_description = grafoProductos.value(s, ECSDI.product_description)
            price = grafoProductos.value(s, ECSDI.price)
            if product_name and product_description:
                return {"product_id": product_id,
                        "product_name": str(product_name),
                        "product_description": str(product_description),
                        "price": float(price)
                        }
    return None


def Compras(idCliente):
    global listCompras
    g_compras = Graph()
    g_compras.parse('database_compras.rdf', format='xml')

    g_devoluciones = Graph()
    g_devoluciones.parse('database_devoluciones.rdf', format='xml')    
    MyCompras = Graph()

    compras_map = {}
    for compra in g_compras.subjects(ECSDI.client_id, Literal(idCliente, datatype=XSD.string)):
        logger.info(compra)
        compra_id = str(g_compras.value(compra, ECSDI.compra_id))
        compras_map[compra_id] = []

        for product_id in g_compras.objects(compra, ECSDI.product_id):
            product_id_str = str(product_id)
            product_info = get_product_info(product_id_str)
            returned = False
            
            for devolucion in g_devoluciones.subjects(ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)):
                if g_devoluciones.value(devolucion, ECSDI.product_id) == product_id:
                    returned = True
                    break
            logger.info(product_info)
            product_details = {
                "product_id": product_id_str,
                "product_name": product_info["product_name"],
                "product_description": product_info["product_description"],
                "price": product_info["price"],
                "returned": returned
            }

            compras_map[compra_id].append(product_details)
            
    listCompras = compras_map
    logger.info(listCompras)
    return compras_map

def verCompras():
    global listCompras
    MyCompras = Compras('02565434C')
    
    g_productos = Graph()
    g_productos.parse('database_producto.rdf', format='xml')
    
    listCompras = []

    for compra in MyCompras.subjects(RDF.type, ECSDI.compra):
        compra_detail = []
        compra_id = str(compra)
        compra_id_literal = str(list(MyCompras.objects(compra, ECSDI.compra_id))[0])
        for s, p, product_id in MyCompras.triples((compra, ECSDI.product_id, None)):
            product_detail = {
                'compra_id': compra_id_literal,
                'product_id': str(product_id),
                'name': '',
                'description': '',
                'price': '',
                'devuelto': False
            }
            for s_prod, p_prod, o_prod in g_productos.triples((ECSDI[product_id], None, None)):
                if p_prod == ECSDI.product_name:
                    product_detail['name'] = str(o_prod)
                elif p_prod == ECSDI.product_description:
                    product_detail['description'] = str(o_prod)
                elif p_prod == ECSDI.price:
                    product_detail['price'] = str(o_prod)
            compra_detail.append(product_detail)
        listCompras.append(compra_detail)
    
    
@app.route('/devolucion/<compra_id>/<idCliente>', methods=['GET', 'POST'])
def devolucion(compra_id, idCliente):
    if request.method == 'POST':
        selected_products = request.form.getlist('products')
        total_price = float(request.form.get('totalPrice', 0))
        client_id = request.form.getlist('idCliente')
        devolver_graph = Graph()
        devolver_graph.bind("ns1", ECSDI)
        if(selected_products):
            devolver_graph.add((ECSDI['DevolverProducto'], RDF.type, ECSDI.DevolverProducto))
            devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
            devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.precioTotal, Literal(total_price, datatype=XSD.float)))
            for product_id in selected_products:
                reason = request.form.get(product_id + "_reason")  # Get the reason for the product
                print(reason)
                devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
                accion = ECSDI['DevolverProducto/']+product_id
                devolver_graph.add((accion,RDF.type, ECSDI.DevolverProducto))
                devolver_graph.add((accion,ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
                devolver_graph.add((accion,ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
                devolver_graph.add((accion,ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
                devolver_graph.add((accion,ECSDI.reason, Literal(reason, datatype=XSD.string)))  # Add the reason to the graph

        print('devolver_graph')
        dev_agent = getAgentInfo(agn.DevolucionAgent, DirectoryAgent, AgentePersonal, getMessageCount())
        logger.info("CREANDO MENSAJE")
        message = build_message(devolver_graph, 
                                perf=ACL.request, 
                                sender=AgentePersonal.uri, 
                                receiver=dev_agent.uri, 
                                msgcnt=getMessageCount(), 
                                content=accion)
        serialized_message = message.serialize(format='xml')
        logger.info(serialized_message)
        logger.info("Enviando RespuestaValoracion")
        response = send_message(message, dev_agent.address)
        response_text = response.serialize(format='xml')
        for s,p,o in response:
            if(p == ECSDI.MensajeOK):
                ok = True
        if ok:    
            global listCompras
            products_details =listCompras.get(compra_id, [])
            
            for product in products_details:
                if product['product_id'] in selected_products:
                        product['returned'] = True

            logger.info('LISTCOMPRAS TO TRUE')
            logger.info(listCompras)
            return "Devoluciones procesadas y guardadas en devoluciones.rdf"
        else:
            return "Devolucion no aceptada"
    
    found_compra_detail = []
    # Fetch compra detail from listCompras
    found_compra_detail = listCompras.get(compra_id, [])
    logger.info('COOOOOMPRAAAAAAAAAA')
    logger.info(found_compra_detail)
    print(idCliente)
    return render_template('devolucion.html', compra_id=compra_id, idCliente=idCliente, products=found_compra_detail)


@app.route('/compras', methods=['GET', 'POST'])
def compras():
    if request.method == 'POST':
        if request.form.get('submit') == 'Submit':
            logger.info(listCompras)
            idCliente = request.form['client_id']
            logger.info(idCliente)
            Compras(idCliente)
            return render_template('comprasUsuario.html', compras=listCompras, idCliente=idCliente)
        else:
            compra_id = request.form.get('compra_id')
            idCliente = request.form.get('idCliente')
            return redirect(url_for('devolucion', compra_id=compra_id, idCliente=idCliente))
    elif request.method == 'GET':
        return render_template('introducirDni.html')
    




@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == "POST":
        product_id = request.form['product_id']
        rating = request.form['rating']
        valoracion = request.form['valoracion']
        client_id = request.form['client_id']
        # Handle form submission here
        logger.info("Recibida peticion de valoracion")
        grafoValoracion = Graph()
        content = ECSDI['RespuestaValoracion' + str(getMessageCount())]
        # content is uriref : http://ONTOLOGIA_ECSDI/RespuestaValoracion1
        grafoValoracion.add((content, RDF.type, ECSDI.RespuestaValoracion))
        grafoValoracion.add((content, ECSDI.compra_id, Literal(compra_to_rate, datatype=XSD.string)))
        grafoValoracion.add((content, ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
        grafoValoracion.add((content, ECSDI.rating, Literal(int(rating), datatype=XSD.int)))
        grafoValoracion.add((content, ECSDI.valoracion_texto, Literal(valoracion, datatype=XSD.string)))
        grafoValoracion.add((content, ECSDI.client_id, Literal(client_id, datatype=XSD.string)))
    
        product_uri = URIRef(product_id)

        #Enviar Valoraciones a ValoracionRecomendacionAgent
        valoracionAgent = getAgentInfo(agn.ValoracionRecomendacionAgent, DirectoryAgent, AgentePersonal, getMessageCount())
        logger.info("CREANDO MENSAJE")
        message = build_message(grafoValoracion, 
                                perf=ACL.request, 
                                sender=AgentePersonal.uri, 
                                receiver=valoracionAgent.uri, 
                                msgcnt=getMessageCount(), 
                                content=content)
        serialized_message = message.serialize(format='xml')
        logger.info(serialized_message)
        logger.info("Enviando RespuestaValoracion")
        logger.info(grafoValoracion.serialize(format='xml'))
        try:
            response = send_message(message, valoracionAgent.address)
            response_text = response.serialize(format='xml')
            for s,p,o in response:
                if(p == RDF.type):
                    typeR = (o)
            if typeR == ECSDI.OK:
                global products_to_rate
                if product_id in products_to_rate:
                    products_to_rate.remove(product_id)

            logger.info("Response received: %s", response_text)
        except Exception as e:
            logger.error("Error sending message: %s", e)
            return "Error in sending message", 500
        
        logger.info("RespuestaValoracion enviada")
        
        return redirect(url_for('feedback'))
    return render_template('feedback.html', products=products_to_rate)


@app.route("/recommend")
def recommend():
    if(not listaDeRecomendaciones):
        print('listaDeRecomendaciones EEMPTY')
    print(listaDeRecomendaciones)
    return render_template('recommendation.html', products=listaDeRecomendaciones)


@app.route("/stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"

#comunicacion entre los agentes, que me llega un rquest 
@app.route("/comm")
def comunicacion():
    """
    Entrypoint de comunicación del agente
    """
    global dsgraph
    global mss_cnt
    global products_to_rate

    logger.info('Peticion de comunicacion recibida')
    message = request.args['content']
    grafoEntrada = Graph()
    grafoEntrada.parse(data=message, format='xml')

    msgdic = get_message_properties(grafoEntrada)

    if msgdic is None:
        # Si no es un sobre valido respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgentePersonal.uri)
    else:
        # Extraemos la performativa del mensaje
        perf = msgdic['performative']

        # Si la performativa es un request
        if perf == ACL.request:
            # Averiguamos el tipo de contenido que tiene
            contenido = msgdic['content']
            accion = grafoEntrada.value(subject=contenido, predicate=RDF.type)
            logger.info('DENTRO IF perf == ACL.request: ACCION:')
            logger.info(accion)
            if accion == ECSDI.PeticionValoracion:
                logger.info("Recibida peticion de valoracion")                
                grafoOK = Graph()
                mensajeOK = "Confirmado"
                content = ECSDI['ok' + str(getMessageCount())]
                grafoOK.add((content, RDF.type, ECSDI.OK))
                grafoOK.add((content, ECSDI.MensajeOK, Literal(mensajeOK, datatype=XSD.string)))
                logger.info("Recivido PeticionValoracion")
                serialize = grafoOK.serialize(format='xml')
                prepare_products_to_rate(grafoEntrada)

                logger.info("Preparando productos para valoración")
                return serialize, 200
            elif accion == ECSDI.ProductsRecommended:
                logger.info("Recibida recomendacion")
                grafoOK = Graph()
                mensajeOK = "Confirmado"
                content = ECSDI['ok' + str(getMessageCount())]
                grafoOK.add((content, RDF.type, ECSDI.OK))
                grafoOK.add((content, ECSDI.MensajeOK, Literal(mensajeOK, datatype=XSD.string)))
                logger.info("Recibido PeticionValoracion")
                serialize = grafoOK.serialize(format='xml')

                save_listaDeProductosRecomm(grafoEntrada)
                
                return serialize, 200
            
    gr = build_message(Graph(), ACL['not-understood'], sender=AgentePersonal.uri, receiver=None, msgcnt=0)
    return gr.serialize(format='xml'), 200

def prepare_products_to_rate(grafoEntrada):
    global products_to_rate
    global compra_to_rate
    global client_to_rate
    logger.info("Productos para valorar preparados.")
    products_to_rate = []
    for s, p, o in grafoEntrada:
        if p == ECSDI.product_id:
            products_to_rate.append(str(o))
        elif p == ECSDI.compra_id:
            compra_to_rate = str(o)
    logger.info(f"Productos para valorar: {products_to_rate}")
    logger.info(f"De la compra: {compra_to_rate}")
    redirect(url_for('feedback'))



def save_listaDeProductosRecomm(grafoRecomendacion):
    logger.info("Recibido resultado de recomendacion")
    global listaDeRecomendaciones
    listaDeRecomendaciones = {}
    logger.info(grafoRecomendacion.serialize(format = 'xml'))
    product_db = Graph()
    product_db.parse("database_producto.rdf", format="xml")
    listProductsId = {}
    # Extract products from grafoRecomendacion
    for s, p, o in grafoRecomendacion:
        # Check if the triple represents a client_id and product_id relationship
        if p == ECSDI.client_id and isinstance(o, Literal):
            client_id = str(o)
            
            listaDeRecomendaciones[client_id] = []

        elif p == ECSDI.product_id and isinstance(o, Literal):
            product_id = str(o)
            product_info = get_product_info(product_id)
            if 'client_id' in locals():
                listaDeRecomendaciones[client_id].append(product_info)

    logger.info(listaDeRecomendaciones)


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
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=(cola1,))
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    
    logger.info('The End')