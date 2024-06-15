from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, idCompra, idProducto, idClient, rate, valoracion):
    g.add((ECSDI[id], RDF.type, ECSDI.valoracion))
    g.add((ECSDI[id], ECSDI.valoracion_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idClient, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.compra_id, Literal(idCompra, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.product_id, Literal(idProducto, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.rating, Literal(rate, datatype=XSD.int)))
    g.add((ECSDI[id], ECSDI.valoracion_texto, Literal(valoracion, datatype=XSD.string)))


if __name__ == '__main__':
    
    g = Graph()

    #                   ID          idCompra    idProducto  idClient,   rate,   valoracion
    add_product(g, 'Valoracion1', 'Compra1', 'B0184OCGAK', '02565434P',5, 'Muy buenos productos')
    add_product(g, 'Valoracion2', 'Compra2', 'B0184OCGAG', '02565434Z',1 , 'Lamentable')
    add_product(g, 'Valoracion3', 'Compra3', 'B0184OCGAP', '02565434C',5, 'A partir de ahora solo comprare aqui')

    g.serialize('database_valoraciones.rdf', format='xml')
