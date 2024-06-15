# ECSDI
La implementación de la práctica de ECSDI.

## Ejecución
Para ejecutar el código, primero debemos abrir una terminal (windows o linux) y situarnos en la carpeta de implementación. Primero debemos ejecutar el Simple Directory, por lo que ponemos en la línea de comandos: python3 SimpleDirectoryService.py --port 9000 --open. Esto ejecutará el servicio directorio, donde se podrán registrar los agentes. 

Para ejecutar el personalUser, que es el que tiene las funcionalidades con los html, debemos ejecutar en otra terminal:

```
Si la terminal se abre desde el mismo ordenador: python3 personalUserAgent.py --port 9001 --dhost localhost --dport 9000 --open
Si la terminal se abre desde otro ordenador conectado a la misma red local: python3 personalUserAgent.py --port 9001 --dhost IpDelSimpleDirectory --dport 9000 --open
```

Para ejecutar el resto de agentes se debe usar el mismo comando que el anterior utilizado cambiando el número de puerto, por ejemplo:
```
Si la terminal se abre desde el mismo ordenador: python3 AgenteBuscador.py --port 9002 --dhost localhost --dport 9000 --open
Si la terminal se abre desde otro ordenador conectado a la misma red local: python3 AgenteBuscador.py --port 9002 --dhost IpDelSimpleDirectory --dport 9000 --open
```

Una vez ejecutados, se debe abrir un navegador desde donde esté ejecutado el personalUserAgent y buscar: localhost:9001/funcionalidad. Por ejemplo, si queremos utilizar el buscador de productos: localhost:9001/search.


## Agentes que se deben usar
* `/AgenteBanco`
* `/AgenteBuscador`
* `/AgenteVendedor`
* `/AgProductosExternos`
* `/ValoracionRecomendacionAgent`
* `/personalUserAgent`
* `/CentrosLogisticos`
* `/Tesorero`
* `/personalRecomendacion`

El resto de archivos python son pruebas e inicializaciones de las bases de datos que utilizamos (create_nombre_database.py).

## Funcionamiento del código

Las funcionalidades de la práctica están especificadas en las rutas del personalUser (app.route('/nombreRuta, methods=['GET', 'POST']'))

Todas ellas contienen un html definido en la carpeta "templates".

Los archivos .rdf son las bases de datos.

La carpeta AgentUtil es necesaria para la comunicación entre agentes. Solo hemos tocado el archivo OntoNamespaces para poner nuestro namespace personalizado.

La carpeta Examples contiene código del profesor que se puede encontrar en su repositorio con ejemplos de agentes, de donde podemos sacar muy útilmente un ejemplo de agente sin funciones adicionales más que las necesarias para que funcione.

La carpeta Python también contiene código del profesor y la carpeta test contienen test de pruebas que no hemos utilizado.

Dentro de cada agente, se manejan las comunicaciones recibidas. Dentro de la ruta "/comm", se mira que accion ha llegado con el último if de nuestros códigos. Si miramos el AgenteBanco.py, en el apartado "/comm", vemos como en el último if aparece: if accion == ECSDI.cobro or accion == ECSDI.paga:
El identificador de la acción está definido por el que mandó la petición, que es otro agente, ya sea el personalUserAgent o cualquier otro. 

Para mandar peticiones, debemos primero construir el mensaje y luego enviarlo. Un ejemplo muy visual de la ruta 'devolucion' del personal User Agent es:
```
	dev_agent = getAgentInfo(agn.DevolucionAgent, DirectoryAgent, AgentePersonal, getMessageCount())
    message = build_message(devolver_graph, 
                            perf=ACL.request, 
                            sender=AgentePersonal.uri, 
                            receiver=dev_agent.uri, 
                            msgcnt=getMessageCount(), 
                            content=accion)
    response = send_message(message, dev_agent.address)
```
Donde:
- agn.DevolucionAgent -> El agente al que queremos enviar la petición (debe estar abierto al enviarle la petición)
- AgentePersonal -> El nombre de nuestro agente definido al inicio del archivo
- devolver_graph -> El grafo que queremos enviar. **SIEMPRE** debe enviarse un grafo.

La forma de debugar el código es con los logger.info, que son básicamente prints con alguna información adicional.