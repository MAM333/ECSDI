from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI
from datetime import datetime, timedelta

def add_product(g, id, idProductos, idCliente, createdAt):
    g.add((ECSDI[id], RDF.type, ECSDI.Search))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idCliente, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.search_id, Literal(id, datatype=XSD.string)))
    for idProducto in idProductos:
        g.add((ECSDI[id], ECSDI.product_id, Literal(idProducto, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.createdAt, Literal(createdAt, datatype=XSD.dateTime)))

if __name__ == '__main__':
    
    g = Graph()
    listProducts = ['B0184OCGAK', 'B0184OCGAG']

    #                ID       idProducto    idCliente     createdAt       
    add_product(g, 'Search1', listProducts, '02565434P', datetime.now())
    add_product(g, 'Search2', ['B0184OCGAG'], '02565434Z', datetime.now())
    add_product(g, 'Search3', ['B0184OCGAP'], '02565434C', datetime.now())

    g.serialize('database_searchHistory.rdf', format='xml')
