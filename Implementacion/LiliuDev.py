from rdflib import Graph, Literal, Namespace
from rdflib.namespace import FOAF, RDF, XSD
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, timedelta, timezone
import random 


ECSDI = Namespace("http://ONTOLOGIA_ECSDI/")

def Compras():
    idCliente = idCliente = '02565434P'
    g_compras = Graph()
    g_compras.parse('database_compras.rdf', format='xml')
    
    MyCompras = Graph()

    for s, p, o in g_compras.triples((None, ECSDI.client_id, Literal(idCliente, datatype=XSD.string))):
        compra_id = s
        MyCompras.add((compra_id, RDF.type, ECSDI.compra))
        MyCompras.add((compra_id, ECSDI.compra_id, Literal(compra_id.split('/')[-1], datatype=XSD.string)))
        
        for compra, pred, product_id in g_compras.triples((compra_id, ECSDI.product_id, None)):
            MyCompras.add((compra_id, ECSDI.product_id, product_id))
    
    return MyCompras

def verCompras():
    MyCompras = Compras()
    
    g_productos = Graph()
    g_productos.parse('database_producto.rdf', format='xml')
    
    listCompras = []

    for compra in MyCompras.subjects(RDF.type, ECSDI.compra):
        compra_detail = []
        compra_id = str(compra)
        compra_id_literal = str(list(MyCompras.objects(compra, ECSDI.compra_id))[0])
        for s, p, product_id in MyCompras.triples((compra, ECSDI.product_id, None)):
            product_detail = {
                'compra_id': compra_id_literal,
                'product_id': str(product_id),
                'name': '',
                'description': '',
                'price': ''
            }
            for s_prod, p_prod, o_prod in g_productos.triples((ECSDI[product_id], None, None)):
                if p_prod == ECSDI.product_name:
                    product_detail['name'] = str(o_prod)
                elif p_prod == ECSDI.product_description:
                    product_detail['description'] = str(o_prod)
                elif p_prod == ECSDI.price:
                    product_detail['price'] = str(o_prod)
            compra_detail.append(product_detail)
        listCompras.append(compra_detail)
    
    return render_template('comprasUsuario.html', compras=listCompras)

# Flask App
app = Flask(__name__)

@app.route('/compras', methods=['GET', 'POST'])
def compras():
    if (request.method == 'POST'):
        compra_id = request.form.get('compra_id')
        return redirect(url_for('devolucion', compra_id=compra_id))

    return verCompras()
 

def processDevolucion(devolucionRequest):
    g_compras = Graph()
    g_compras.parse('database_compras.rdf', format='xml')
    
    accepted_graph = Graph()
    accepted_graph.bind("ns1", ECSDI)

    precio_total = 0.0
    compra_id = list(devolucionRequest.objects(None, ECSDI.compra_id))[0]

    for s, p, o in devolucionRequest.triples((None, ECSDI.precioTotal, None)):
        precio_total = o

    query = """
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?fecha_limite_devolucion
    WHERE {
        ?compra ns1:compra_id ?compra_id ;
                ns1:fecha_limite_devolucion ?fecha_limite_devolucion .
        FILTER (?compra_id = """ + f'"{compra_id}"' + """)
    }
    """

    qres = g_compras.query(query)
    b = False
    for row in qres:
        fecha_limite_devolucion = row.fecha_limite_devolucion.toPython()
        print(f"Fecha limite devolucion: {fecha_limite_devolucion}")
        if datetime.now() <= fecha_limite_devolucion:
            b = True
            subject = ECSDI['DevolucionAccepted']
            accepted_graph.add((subject, RDF.type, ECSDI.DevolucionAccepted))
            accepted_graph.add((subject,  ECSDI.compra_id, compra_id))
            accepted_graph.add((subject, ECSDI.precioTotal, precio_total))
            for s, p, o in devolucionRequest:
                if p == ECSDI.product_id:
                    product_id = str(o)
                    accepted_graph.add((subject, ECSDI.product_id, o))
                    devolucion_uri = ECSDI[f'DevolucionAccepted/{product_id}']
                    accepted_graph.add((devolucion_uri, RDF.type, ECSDI.DevolucionAccepted))
                    accepted_graph.add((devolucion_uri, ECSDI.compra_id, compra_id))
                    accepted_graph.add((devolucion_uri, ECSDI.product_id, o))                    
                    # Add reason for each product
                    reason = list(devolucionRequest.objects(s, ECSDI.reason))
                    if reason:
                        accepted_graph.add((devolucion_uri, ECSDI.reason, reason[0]))
            print('accepted_graph')
            print(accepted_graph.serialize(format='xml'))
            
    return b

@app.route('/devolucion/<compra_id>', methods=['GET', 'POST'])
def devolucion(compra_id):
    if request.method == 'POST':
        selected_products = request.form.getlist('products')
        total_price = float(request.form.get('totalPrice', 0))

        devolver_graph = Graph()
        devolver_graph.bind("ns1", ECSDI)
        if(selected_products):
            devolver_graph.add((ECSDI['DevolverProducto'], RDF.type, ECSDI.DevolverProducto))
            devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
            devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.precioTotal, Literal(total_price, datatype=XSD.float)))
            for product_id in selected_products:
                reason = request.form.get(product_id + "_reason")  # Get the reason for the product
                print(reason)
                devolver_graph.add((ECSDI['DevolverProducto'], ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
                accion = ECSDI['DevolverProducto/']+product_id
                devolver_graph.add((accion,RDF.type, ECSDI.DevolverProducto))
                devolver_graph.add((accion,ECSDI.compra_id, Literal(compra_id, datatype=XSD.string)))
                devolver_graph.add((accion,ECSDI.product_id, Literal(product_id, datatype=XSD.string)))
                devolver_graph.add((accion,ECSDI.reason, Literal(reason, datatype=XSD.string)))  # Add the reason to the graph

        print('devolver_graph')
        print(devolver_graph.serialize(format='xml'))
        b = processDevolucion(devolver_graph)
        if(b):
            return "Devoluciones procesadas y guardadas en devoluciones.rdf"
        return "Fuera plazo"

    # Fetch compra details for display
    MyCompras = Compras('02565434P')  # Assuming the client ID is constant for this example
    compra_detail = []
    
    g_productos = Graph()
    g_productos.parse('database_producto.rdf', format='xml')
    
    for compra in MyCompras.subjects(RDF.type, ECSDI.compra):
        compra_id_literal = str(list(MyCompras.objects(compra, ECSDI.compra_id))[0])
        if compra_id_literal == compra_id:
            for s, p, product_id in MyCompras.triples((compra, ECSDI.product_id, None)):
                product_detail = {
                    'compra_id': compra_id_literal,
                    'product_id': str(product_id),
                    'name': '',
                    'description': '',
                    'price': ''
                }
                for s_prod, p_prod, o_prod in g_productos.triples((ECSDI[product_id], None, None)):
                    if p_prod == ECSDI.product_name:
                        product_detail['name'] = str(o_prod)
                    elif p_prod == ECSDI.product_description:
                        product_detail['description'] = str(o_prod)
                    elif p_prod == ECSDI.price:
                        product_detail['price'] = str(o_prod)
                compra_detail.append(product_detail)

    return render_template('devolucion.html', compra_id=compra_id, products=compra_detail)


def recommending(idClient):
    print("Recibida petición de recomendación")
    recommendation_graph = Graph()

    try:
        # Load data from database_compras.rdf
        database_compras = Graph()
        database_compras.parse("database_compras.rdf")

        # Load data from database_historialBusqueda.rdf
        database_historialBusqueda = Graph()
        database_historialBusqueda.parse("database_searchHistory.rdf")

        database_product = Graph()
        database_product = database_product.parse("database_producto.rdf")
    except Exception as e:
        print(f"Error parsing RDF files: {e}")
        return recommendation_graph

    products_client = Graph()
    content = ECSDI['PossibleReomendation']
    for s, p, o in database_compras.triples((None, ECSDI.client_id, Literal(idClient, datatype=XSD.string))):
        compra_id = s
        for compra, pred, product_id in database_compras.triples((compra_id, ECSDI.product_id, None)):
            products_client.add((content, ECSDI.product_id, product_id))

    for s, p, o in database_historialBusqueda.triples((None, ECSDI.client_id, Literal(idClient, datatype=XSD.string))):
        search_id = s
        for compra, pred, product_id in database_historialBusqueda.triples((search_id, ECSDI.product_id, None)):
            products_client.add((content, ECSDI.product_id, product_id))

    print(products_client.serialize(format = 'xml'))
    
    products_list = []
    # Convert products to a list and randomly select up to 5 products if more than 5
    products_list = list(products_client.objects(subject=content, predicate=ECSDI.product_id))
    if len(products_list) > 5:
        products_list = random.sample(products_list, 5)
    # Add selected products with details to recommendation_graph
    accion = ECSDI['ProductsRecommended']
    recommendation_graph.add((accion, RDF.type, ECSDI.ProductsRecommended))

    for product_id in products_list:
        recommendation_graph.add((accion, ECSDI.product_id, product_id))

        """ Add product details
        for pred in [ECSDI.product_name, ECSDI.product_description, ECSDI.price]:
            for s, p, o in database_product.triples((product_id, pred, None)):
                recommendation_graph.add((accion, pred, o))"""

    return recommendation_graph

@app.route('/recommend', methods=['GET', 'POST'])
def recommend():
    recommendation_graph = recommending("02565434P")
    print(recommendation_graph.serialize(format="xml"))
    return "Done"


def comprobar_y_valorar():
    client_id = "02565434P"  # The specific tarjeta to filter by    
    # Load purchase history
    graph_compras = Graph()
    try:
        with open('./database_compras.rdf') as ontology_file:
            print("Comprobando productos comprados")
            graph_compras.parse(ontology_file, format='xml')
    except FileNotFoundError:
        print("Database file for purchases not found.")
        return
    except Exception as e:
        print(f"Error loading purchase history: {str(e)}")
        return

    # SPARQL query to fetch the latest compra for the client
    print('ANTER QUERY')

    query = f"""
    PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
    SELECT ?compra_id ?fecha_envio ?product_id
    WHERE {{
        ?compra rdf:type ns1:compra .
        ?compra ns1:client_id "{client_id}"^^<http://www.w3.org/2001/XMLSchema#string> . 
        ?compra ns1:compra_id ?compra_id .
        ?compra ns1:fecha_envio ?fecha_envio .
        ?compra ns1:product_id ?product_id .
    }}
    ORDER BY DESC(?fecha_envio)
    LIMIT 1
    """

    # Execute the simplified query
    qres = graph_compras.query(query)

    productos_compras = {
        "compra_id": None,
        "fecha_envio": None,
        "product_ids": []
    }

    for row in qres:
        productos_compras["compra_id"] = row.compra_id
        productos_compras["fecha_envio"] = str(row.fecha_envio)
        productos_compras["product_ids"].append(row.product_id)

    compra_id = productos_compras["compra_id"]
    productos_compras_ids = productos_compras["product_ids"]
    fecha_envio = productos_compras["fecha_envio"]
    print(f"Compra: {compra_id}, Fecha envio: {fecha_envio}")
    
    # Get the current time
    current_time = datetime.now()

    # Parse fecha_envio and add 5 minutes
    if(fecha_envio == None):
        return "No hay fecha Envio"

    fecha_envio = datetime.strptime(productos_compras["fecha_envio"], "%Y-%m-%dT%H:%M:%S.%f")
    fecha_envio_plus_5 = fecha_envio + timedelta(minutes=5)
    to_rate = current_time > fecha_envio_plus_5
    print('DDDDDDDDAAAAAAAAAAAAAAAAAAAAAAATTTTTTTTTTTTTTTTEEEEEEEEEEEEEEEESSSSSSS')
    print(current_time)
    print(fecha_envio_plus_5)

    if (not to_rate):
        return "No hay nuevos productos para valorar"
    
    # Load valuation history
    existing_valorations_database = False
    graph_valoraciones = Graph()
    try:
        graph_valoraciones.parse('./database_valoraciones.rdf', format='xml')
        print("comprobar_y_valorar Cargando base de datos de valoraciones")
        existing_valorations_database = True
    except FileNotFoundError:
        print("Base de datos de valoraciones no encontrada, creando una nueva")
        graph_valoraciones.bind('rdf', RDF)
        graph_valoraciones.bind('ecsdi', ECSDI)
    except Exception as e:
        print(f"Error loading valuation database: {str(e)}")
        return

    productos_sin_valoracion = []
    if to_rate:
        contenido = ECSDI['PeticionValoracion']
        grafoContenido = Graph()
        grafoContenido.add((contenido, RDF.type, ECSDI.PeticionValoracion))
        grafoContenido.add((contenido, ECSDI.compra, compra_id))
        if existing_valorations_database:
            # SPARQL query to fetch valorations for the specific compra_id and product_ids
            valorations_query = f"""
            PREFIX ns1: <http://ONTOLOGIA_ECSDI/>
            SELECT ?product_id
            WHERE {{
            ?valoracion rdf:type ns1:valoracion .
            ?valoracion ns1:compra_id "{compra_id}" .
            ?valoracion ns1:product_id ?product_id .
            }}
            """
            # Execute the query
            valorations_qres = graph_valoraciones.query(valorations_query)

            productos_valorados = {
                "compra_id": compra_id,
                "product_ids": []
            }

            for row in valorations_qres:
                productos_valorados["product_ids"].append(row.product_id)

            productos_valorados_ids = productos_valorados["product_ids"]
            products_to_rate = [pid for pid in productos_compras_ids if pid not in productos_valorados_ids]
            productos_sin_valoracion =  products_to_rate
            for product_id in productos_sin_valoracion:
                grafoContenido.add((contenido, ECSDI.product_id, product_id))
        else:
            productos_sin_valoracion = productos_compras_ids
            for product_id in productos_sin_valoracion:
                grafoContenido.add((contenido, ECSDI.product_id, product_id))
    return grafoContenido

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    recommendation_graph =     comprobar_y_valorar()
    if isinstance(recommendation_graph, Graph):
        print(recommendation_graph.serialize(format='xml'))
        return "Valoracion"
    else:
        return recommendation_graph


if __name__ == '__main__':
    app.run(debug=True)
