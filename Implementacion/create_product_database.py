from rdflib import FOAF, XSD, Namespace, Graph, Literal, RDF
from AgentUtil.OntoNamespaces import ECSDI

def add_product(g, product_id, product_name, product_description, price, shop):
    print(ECSDI[product_id])#crear un nou namesapace per cada producte 
    print(ECSDI.product)
    g.add((ECSDI[product_id], RDF.type, ECSDI.product))
    g.add((ECSDI[product_id], ECSDI.product_name, Literal(product_name, datatype=XSD.string)))
    g.add((ECSDI[product_id], ECSDI.product_id, Literal(product_id)))
    g.add((ECSDI[product_id], ECSDI.product_description, Literal(product_description, datatype=XSD.string)))
    g.add((ECSDI[product_id], ECSDI.price, Literal(price)))
    g.add((ECSDI[product_id], ECSDI.shop, Literal(shop, datatype=XSD.string)))

if __name__ == '__main__':
    
    g = Graph()

    add_product(g, 'B0184OCGAK', 'Boli', 'Bon producte', 10, None)
    add_product(g, 'B0184OCGAG', 'Kindle', 'Bon producte', 50, None)
    add_product(g, 'B0184OCGAP', 'Kindle2', 'Bon producte', 50, None)
    add_product(g, 'B0184OCGUP', 'Kindle3', 'Bon producte', 50, None)
    add_product(g, 'B0184OCGUA', 'KindleExterno', 'Bon producte', 50, 'TiendaExterna1')

    g.serialize('database_producto.rdf', format='xml')
