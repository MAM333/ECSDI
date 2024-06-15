from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI
from datetime import datetime, timedelta

def add_product(g, id, idProductos, idCliente, createdAt, fechaEnvio, fechaLimiteDevolucion):
    g.add((ECSDI[id], RDF.type, ECSDI.compra))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idCliente, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.compra_id, Literal(id, datatype=XSD.string)))
    for idProducto in idProductos:
        g.add((ECSDI[id], ECSDI.product_id, Literal(idProducto, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.created_at, Literal(createdAt, datatype=XSD.dateTime)))
    g.add((ECSDI[id], ECSDI.fecha_envio, Literal(fechaEnvio, datatype=XSD.dateTime)))
    g.add((ECSDI[id], ECSDI.fecha_limite_devolucion, Literal(fechaLimiteDevolucion, datatype=XSD.dateTime)))

if __name__ == '__main__':
    
    g = Graph()
    listProducts = ['B0184OCGAK', 'B0184OCGAG']

    #                ID       idProducto    idCliente     createdAt             fechaEnvio(llegada)                fechaLimiteDevolucion
    add_product(g, 'Compra1', listProducts, '02565434P', datetime.now(), datetime.now() , datetime.now() + timedelta(days=15))
    add_product(g, 'Compra2', ['B0184OCGAG'], '02565434Z', datetime.now(), datetime.now() , datetime.now() + timedelta(days=15))
    add_product(g, 'Compra3', ['B0184OCGAP'], '02565434C', datetime.now(), datetime.now() , datetime.now() + timedelta(days=15))
    add_product(g, 'Compra4', ['B0184OCGAP', 'B0184OCGAG'], '02565434C', datetime.now(), datetime.now() , datetime.now() + timedelta(days=15))

    g.serialize('database_compras.rdf', format='xml')
