from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_centros(g, centros_id, direccion, listaProductos):
    # Crear el namespace para el centro logístico
    ns_centro = ECSDI[centros_id]
    print(ns_centro)
    
    # Añadir información del centro logístico
    g.add((ns_centro, RDF.type, ECSDI.centro_logistico))
    g.add((ns_centro, ECSDI.centros_id, Literal(centros_id, datatype=XSD.string)))
    g.add((ns_centro, ECSDI.direccion, Literal(direccion, datatype=XSD.string)))
    
    
    # Añadir la lista de productos asociados al centro logístico
    for producto_id in listaProductos:
        g.add((ns_centro, ECSDI.tieneProducto, Literal(producto_id, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    add_centros(g, 'CL184OCGAK', 'Girona', ['B0184OCGUP', 'B0184OCGAG'])
    add_centros(g, 'CL184OCGAG', 'Castelldefels', ['B0184OCGUP', 'B0184OCGAG', 'B0184OCGAP'])
    add_centros(g, 'CL184OCGAP', 'Barcelona', ['B0184OCGUP'])
    add_centros(g, 'CL184OCGUP', 'Lleida', ['B0184OCGUP', 'B0184OCGAG', 'B0184OCGAP', 'B0184OCGAK'])
    add_centros(g, 'CL184OCGUZ', 'Tarragona', ['B0184OCGUP', 'B0184OCGAP'])



    g.serialize('../database_centrosLogisticos.rdf', format='xml')
