from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, id, idCliente, precioTotal, idCompra):
    g.add((ECSDI[id], RDF.type, ECSDI.cobro_pendiente))
    g.add((ECSDI[id], ECSDI.client_id, Literal(idCliente, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.cobro_pendiente_id, Literal(id, datatype=XSD.string)))
    g.add((ECSDI[id], ECSDI.precio_total, Literal(precioTotal)))
    g.add((ECSDI[id], ECSDI.compra_id, Literal(idCompra, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    #               idCobro idCliente precioTotal  idCompra
    add_product(g, 'Cobro1', '02565434P', 40,   'Compra1')
    add_product(g, 'Cobro2', '02565434Z', 30,   'Compra2')
    add_product(g, 'Cobro3', '02565434Z', 55,   'Compra3')
    add_product(g, 'Cobro4', '02565434Z', 55,   'Compra4')

    g.serialize('database_cobros_pendientes.rdf', format='xml')
