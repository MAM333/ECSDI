from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, idProducts, idClient, enviado, precioTotal):
    g.add((ECSDI[id], RDF.type, ECSDI.lote))
    g.add((ECSDI[id], ECSDI.lote_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idClient, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.enviado, Literal(enviado, datatype=XSD.boolean)))
    g.add((ECSDI[id], ECSDI.precio_total, Literal(precioTotal)))

    for producto_id in idProducts:
        g.add((ECSDI[id], ECSDI.product_id, Literal(producto_id, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    #                  ID   idProductos     idClient, enviado?
    add_product(g, 'Lote1', ['B0184OCGAK'],  '02565434P', True, 70)
    add_product(g, 'Lote2', ['B0184OCGAK', 'B0184OCGAG'], '02565434Z', True, 80)
    add_product(g, 'Lote3', ['B0184OCGAK', 'B0184OCGAG', 'B0184OCGAP'], '02565434P', False, 110)

    g.serialize('database_lotes.rdf', format='xml')
