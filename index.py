import json
import random
import hashlib
import mysql.connector
import base64
import shutil
import secrets
from PIL import Image
from datetime import datetime
from pathlib import Path
from bottle import route, run, template, post, request, static_file, get


def loadDatabaseSettings(pathjs):
    pathjs = Path(pathjs)
    sjson = False
    if pathjs.exists():
        with pathjs.open() as data:
            sjson = json.load(data)
    return sjson


def getToken():
    return secrets.token_hex(32)


@get('/')
def hola_mundo():
    return "Hola mundo, atentamente Equipo Ladrillo!"


@post('/Registro')
def Registro():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    if not request.json:
        return {"R": -1}

    R = 'uname' in request.json and 'email' in request.json and 'password' in request.json
    if not R:
        return {"R": -1}

    try:
        with db.cursor() as cursor:
            cursor.execute('insert into Usuario values(null,%s,%s,md5(%s))',
                           (request.json["uname"], request.json["email"], request.json["password"]))
            R = cursor.lastrowid
            db.commit()
        db.close()
    except Exception as e:
        print(e)
        return {"R": -2}

    return {"R": 0, "D": R}


@post('/Login')
def Login():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    if not request.json:
        return {"R": -1}

    R = 'uname' in request.json and 'password' in request.json
    if not R:
        return {"R": -1}

    try:
        with db.cursor() as cursor:
            cursor.execute('Select id from Usuario where uname = %s and password = md5(%s)',
                           (request.json["uname"], request.json["password"]))
            R = cursor.fetchone()
    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}

    if not R:
        db.close()
        return {"R": -3}

    T = getToken()
    try:
        with db.cursor() as cursor:
            cursor.execute('Delete from AccesoToken where id_Usuario = %s', (R[0],))
            cursor.execute('insert into AccesoToken values(%s,%s,now())', (R[0], T))
            db.commit()
            db.close()
            return {"R": 0, "D": T}
    except Exception as e:
        print(e)
        db.close()
        return {"R": -4}


@post('/Imagen')
def Imagen():
    tmp = Path('tmp')
    if not tmp.exists():
        tmp.mkdir()
    img = Path('img')
    if not img.exists():
        img.mkdir()

    if not request.json:
        return {"R": -1}

    R = 'name' in request.json and 'data' in request.json and 'ext' in request.json and 'token' in request.json
    if not R:
        return {"R": -1}

    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    TKN = request.json['token']

    try:
        with db.cursor() as cursor:
            cursor.execute('select id_Usuario from AccesoToken where token = %s', (TKN,))
            usuario = cursor.fetchone()
            if not usuario:
                db.close()
                return {"R": -3}
    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}

    id_Usuario = usuario[0]
    ext_permitidas = ["jpg", "jpeg", "png", "gif"]
    ext = request.json["ext"].lower()
    if ext not in ext_permitidas:
        db.close()
        return {"R": -5, "E": "tipo de archivo no permitido"}
    tmp_path = f"tmp/{id_Usuario}"
    with open(tmp_path, "wb") as imagen:
        imagen.write(base64.b64decode(request.json['data'].encode()))
    try:
        with Image.open(tmp_path) as img:
            mime_detectado = img.format.lower()
    except Exception:
        db.close()
        Path(tmp_path).unlink()
        return {"R": -6, "E": "archivo inválido o corrupto"}
    if mime_detectado not in ["jpeg", "png", "gif"]:
        db.close()
        Path(tmp_path).unlink()
        return {"R": -6, "E": "tipo de imagen no permitido"}

    try:
        with db.cursor() as cursor:
            cursor.execute('insert into Imagen values(null,%s,"img/",%s)',
                           (request.json["name"], id_Usuario))
            cursor.execute('select max(id) from Imagen where id_Usuario = %s', (id_Usuario,))
            R = cursor.fetchone()
            idImagen = R[0]
            cursor.execute('update Imagen set ruta = %s where id = %s',
                           (f'img/{idImagen}.{request.json["ext"]}', idImagen))
            db.commit()

        shutil.move(f'tmp/{id_Usuario}', f'img/{idImagen}.{request.json["ext"]}')
        return {"R": 0, "D": idImagen}
    except Exception as e:
        print(e)
        db.close()
        return {"R": -3}


@post('/Descargar')
def Descargar():
    dbcnf = loadDatabaseSettings('db.json')
    db = mysql.connector.connect(
        host='localhost', port=dbcnf['port'],
        database=dbcnf['dbname'],
        user=dbcnf['user'],
        password=dbcnf['password']
    )

    if not request.json:
        return {"R": -1}

    R = 'token' in request.json and 'id' in request.json
    if not R:
        return {"R": -1}

    TKN = request.json['token']
    idImagen = request.json['id']

    try:
        with db.cursor() as cursor:
            cursor.execute('select id_Usuario from AccesoToken where token = %s', (TKN,))
            usuario = cursor.fetchall()

        if not usuario:
            db.close()
            return {"R": -3}

        with db.cursor() as cursor:
            cursor.execute('Select name,ruta,id_Usuario from Imagen where id = %s', (idImagen,))
            img = cursor.fetchall()

        if not img or img[0][2] != usuario[0][0]:
            db.close()
            return {"R": -4}

        return static_file(img[0][1], Path(".").resolve())


    except Exception as e:
        print(e)
        db.close()
        return {"R": -2}


if __name__ == '__main__':
    run(host='0.0.0.0', port=8080, debug=False)
