from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, dinero):
    g.add((ECSDI[id], RDF.type, ECSDI.dinero))
    g.add((ECSDI[id], ECSDI.dinero_valor, Literal(dinero)))

if __name__ == '__main__':
    
    g = Graph()

    add_product(g, 1000)

    g.serialize('database_dinero.rdf', format='xml')
