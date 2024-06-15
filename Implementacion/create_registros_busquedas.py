from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, idClient, idProduct):
    g.add((ECSDI[id], RDF.type, ECSDI.registro_busqueda))
    g.add((ECSDI[id], ECSDI.registro_busqueda_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idClient, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.product_id, Literal(idProduct, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    #                  ID          idCliente    idProducto
    add_product(g, 'Busqueda1', '02565434P', 'B0184OCGAK')
    add_product(g, 'Busqueda2', '02565434Z', 'B0184OCGAG')
    add_product(g, 'Busqueda3', '02565434Z', 'B0184OCGAP')

    g.serialize('database_registros_busquedas.rdf', format='xml')
