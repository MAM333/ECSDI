# -*- coding: utf-8 -*-
"""
filename: ACLMessages

Utilidades para tratar los mensajes FIPA ACL

Created on 08/02/2014 ###

@author: javier
"""
__author__ = 'javier'

from rdflib import FOAF, Graph, Literal, Namespace, URIRef
import requests
from rdflib.namespace import RDF, OWL
from AgentUtil.ACL import ACL
from AgentUtil.Agent import Agent
from AgentUtil.DSO import DSO

agn = Namespace("http://www.agentes.org#")

def build_message(gmess, perf, sender=None, receiver=None,  content=None, msgcnt=0):
    """
    Construye un mensaje como una performativa FIPA acl
    Asume que en el grafo que se recibe esta ya el contenido y esta ligado al
    URI en el parametro contenido

    :param gmess: grafo RDF sobre el que se deja el mensaje
    :param perf: performativa del mensaje
    :param sender: URI del sender
    :param receiver: URI del receiver
    :param content: URI que liga el contenido del mensaje
    :param msgcnt: numero de mensaje
    :return:
    """
    # Añade los elementos del speech act al grafo del mensaje
    mssid = f'message-{sender.__hash__()}-{msgcnt:04}'
    # No podemos crear directamente una instancia en el namespace ACL ya que es un ClosedNamedspace
    ms = URIRef(mssid)
    gmess.bind('acl', ACL)
    gmess.add((ms, RDF.type, OWL.NamedIndividual)) # Declaramos la URI como instancia
    gmess.add((ms, RDF.type, ACL.FipaAclMessage))
    gmess.add((ms, ACL.performative, perf))
    gmess.add((ms, ACL.sender, sender))
    if receiver is not None:
        gmess.add((ms, ACL.receiver, receiver))
    if content is not None:
        gmess.add((ms, ACL.content, content))
        
    return gmess


def send_message(gmess, address):
    msg = gmess.serialize(format='xml')
    #print(f"Sending message: {msg}")  # Print the message being sent
    try:
        r = requests.get(address, params={'content': msg})

        # Print the response received
        #print(f"Received response: {r.text}")

        # Procesa la respuesta y la retorna como resultado como grafo
        gr = Graph()
        gr.parse(data=r.text, format='xml')
        return gr
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return None
"""
def send_message(gmess, address):
    msg = gmess.serialize(format='xml')
    r = requests.get(address, params={'content': msg})

    # Procesa la respuesta y la retorna como resultado como grafo
    gr = Graph()
    gr.parse(data=r.text, format='xml')
    return gr
"""
def get_message_properties(msg):
    """
    Extrae las propiedades de un mensaje ACL como un diccionario.
    Del contenido solo saca el primer objeto al que apunta la propiedad

    Los elementos que no estan, no aparecen en el diccionario
    """
    props = {'performative': ACL.performative, 'sender': ACL.sender,
             'receiver': ACL.receiver, 'ontology': ACL.ontology,
             'conversation-id': ACL['conversation-id'],
             'in-reply-to': ACL['in-reply-to'], 'content': ACL.content}

    msgdic = {} # Diccionario donde se guardan los elementos del mensaje

    # Extraemos la parte del FipaAclMessage del mensaje
    valid = msg.value(predicate=RDF.type, object=ACL.FipaAclMessage)

    # Extraemos las propiedades del mensaje
    if valid is not None:
        for key in props:
            val = msg.value(subject=valid, predicate=props[key])
            if val is not None:
                msgdic[key] = val
    return msgdic

def registerAgent(agent, directoryAgent, typeOfAgent, messageCount):
    gmess = Graph()

    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    reg_obj = agn[agent.name + '-Register']
    gmess.add((reg_obj, RDF.type, DSO.Register))
    gmess.add((reg_obj, DSO.Uri, agent.uri))
    gmess.add((reg_obj, FOAF.name, Literal(agent.name)))
    gmess.add((reg_obj, DSO.Address, Literal(agent.address)))
    gmess.add((reg_obj, DSO.AgentType, typeOfAgent))
    # Lo metemos en un envoltorio FIPA-ACL y lo enviamos
    gr = send_message(
        build_message(gmess, perf=ACL.request,
                      sender=agent.uri,
                      receiver=directoryAgent.uri,
                      content=reg_obj,
                      msgcnt=messageCount),
        directoryAgent.address)
    return gr

def getAgentInfo(agentType, directoryAgent, sender, messageCount):
    gmess = Graph()
    gmess.bind('foaf', FOAF)
    gmess.bind('dso', DSO)
    ask_obj = agn[sender.name + '-Search']

    gmess.add((ask_obj, RDF.type, DSO.Search))
    gmess.add((ask_obj, DSO.AgentType, agentType))
    gr = send_message(
        build_message(gmess, perf=ACL.request, sender=sender.uri, receiver=directoryAgent.uri, msgcnt=messageCount,
                      content=ask_obj),
        directoryAgent.address
    )
    dic = get_message_properties(gr)
    content = dic['content']

    address = gr.value(subject=content, predicate=DSO.Address)
    url = gr.value(subject=content, predicate=DSO.Uri)
    name = gr.value(subject=content, predicate=FOAF.name)

    return Agent(name, url, address, None)
