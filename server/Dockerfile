# La imagen del servidor. Pequeña a propósito: Python, las tres dependencias
# y el código. Corre como un usuario normal, no como root.
FROM python:3.12-slim

WORKDIR /app

# Primero las dependencias, que cambian poco: así la capa queda cacheada y
# reconstruir tras tocar el código tarda segundos.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY contaserver/ contaserver/

# Un usuario sin privilegios. Si algún día alguien se cuela por la API, que
# se encuentre con un usuario que no puede tocar nada del sistema.
RUN useradd --create-home contaxcell
USER contaxcell

EXPOSE 8000

# --proxy-headers hace que la IP que ve la API sea la de quien llama de
# verdad, no la del Caddy de delante; sin eso, el contador de intentos vería
# siempre la misma IP y bloquearía a todo el mundo a la vez. El precio es que
# la API se cree esas cabeceras, así que el puerto 8000 NO puede publicarse
# más allá de 127.0.0.1 (el docker-compose ya lo ata ahí).
CMD ["uvicorn", "contaserver.aplicacion:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
