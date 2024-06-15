from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI
from datetime import datetime, timedelta

def add_product(g, id, idCompra, idProducto, idCliente, razon, fechaCreacion):
    g.add((ECSDI[id], RDF.type, ECSDI.devolucion))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idCliente, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.devolucion_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.compra_id, Literal(idCompra, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.product_id, Literal(idProducto, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.razon, Literal(razon, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.created_at, Literal(fechaCreacion, datatype=XSD.dateTime)))

if __name__ == '__main__':
    
    g = Graph()

    #                ID       idCompra      idProducto    idCliente     razon       fechaCreacion        
    add_product(g, 'Devolucion1', 'Compra1', 'B0184OCGAK', '02565434P','noGustar', datetime.now())
    add_product(g, 'Devolucion2', 'Compra2', 'B0184OCGAG', '02565434Z','noGustar', datetime.now())
    add_product(g, 'Devolucion3', 'Compra3', 'B0184OCGAP', '02565434C','noGustar', datetime.now())

    g.serialize('database_devoluciones.rdf', format='xml')
