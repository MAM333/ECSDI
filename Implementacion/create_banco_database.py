from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, cuenta_banc, dinero):
    g.add((ECSDI[cuenta_banc], RDF.type, ECSDI.cuenta_banc))
    g.add((ECSDI[cuenta_banc], ECSDI.cuenta_banc, Literal(cuenta_banc, datatype=XSD.string)))
    g.add((ECSDI[cuenta_banc], ECSDI.dinero, Literal(dinero)))

if __name__ == '__main__':
    
    g = Graph()

    add_product(g, "ES962100898922113", 1000)
    add_product(g, "ES962100898922114", 90)
    add_product(g, "ES962100898922115", 100)

    g.serialize('database_banco.rdf', format='xml')
