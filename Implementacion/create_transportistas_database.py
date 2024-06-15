from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, disponibilidad, localizacion):
    g.add((ECSDI[id], RDF.type, ECSDI.transportista))
    g.add((ECSDI[id], ECSDI.transportista_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.disponibilidad, Literal(disponibilidad, datatype=XSD.boolean)))
    g.add((ECSDI[id], ECSDI.localizacion, Literal(localizacion, datatype=XSD.string)))


if __name__ == '__main__':
    
    g = Graph()

    #                   ID       disponibilidad localizacion
    add_product(g, 'Transportista1', True, 'Barcelona')
    add_product(g, 'Transportista2', True, 'Castelldefels')
    add_product(g, 'Transportista3', False, 'Girona')

    g.serialize('database_transportistas.rdf', format='xml')
