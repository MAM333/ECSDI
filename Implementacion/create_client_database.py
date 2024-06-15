from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, cuenta_banc, direccion):
    g.add((ECSDI[id], RDF.type, ECSDI.client))
    g.add((ECSDI[id], ECSDI.cuenta_banc, Literal(cuenta_banc, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.client_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.client_direction, Literal(direccion, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    #                  ID          Cuenta bancaria         Direccion
    add_product(g, '02565434P', 'ES962100898922113', 'Castelldefels')
    add_product(g, '02578760P', 'ES962100898922113', 'Castelldefels')
    add_product(g, '02565434Z', 'ES962100898922114', 'Barcelona')
    add_product(g, '02565434C', 'ES962100898922115', 'Girona')

    g.serialize('database_client.rdf', format='xml')
