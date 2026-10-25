#!/usr/bin/env python3
"""Recopilador de subastas judiciales del CSV oficial. Solo datos reales.
Uso: python3 recopilador_subastas.py actualizar [--destino DIR]
     python3 recopilador_subastas.py servir [--destino DIR] [--puerto 8765]
"""
import argparse,csv,datetime as dt,hashlib,http.server,io,json,os,pathlib,sys,tempfile,urllib.error,urllib.request
URL='https://catalogodatos.justicia.es/csv/Subastas_Judiciales.csv'
MAX_BYTES=200*1024*1024

def actualizar(dest):
    dest.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(URL,headers={'User-Agent':'SubastaRadarPro/1.0 (open-data client)','Accept':'text/csv,*/*'})
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            data=r.read(MAX_BYTES+1)
            if len(data)>MAX_BYTES: raise ValueError('Archivo supera 200 MB; no se ha guardado')
            content_type=r.headers.get('Content-Type','')
        if not data: raise ValueError('Descarga vacía')
        if data[:100].lstrip().lower().startswith((b'<!doctype html',b'<html',b'<?xml')): raise ValueError('La fuente devolvió HTML/XML, no un CSV')
        text=None
        for enc in ('utf-8-sig','cp1252'):
            try:text=data.decode(enc);break
            except UnicodeDecodeError:pass
        if text is None:raise ValueError('Codificación no reconocida')
        sample=text[:10000]
        dialect=csv.Sniffer().sniff(sample,delimiters=',;\t')
        reader=csv.DictReader(io.StringIO(text),dialect=dialect)
        fields=reader.fieldnames or []
        if len(fields)<2:raise ValueError('No se detectaron suficientes columnas CSV')
        if any(not (f or '').strip() for f in fields):raise ValueError('Cabeceras CSV vacías')
        count=0
        for row in reader:
            if any(str(v or '').strip() for v in row.values()):count+=1
        if count==0:raise ValueError('No hay registros válidos')
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        metadata={'fuente':URL,'descargado_utc':now,'registros':count,'columnas':fields,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'tipo_contenido':content_type,'cobertura':'Solo subastas judiciales del conjunto de datos del Ministerio de Justicia; no equivale a todo el BOE'}
        for name,payload in [('subastas_oficiales.csv',data),('estado.json',json.dumps(metadata,ensure_ascii=False,indent=2).encode('utf-8'))]:
            fd,tmp=tempfile.mkstemp(dir=dest,prefix='.tmp_')
            try:
                with os.fdopen(fd,'wb') as f:f.write(payload)
                os.replace(tmp,dest/name)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        print(json.dumps(metadata,ensure_ascii=False,indent=2));return 0
    except Exception as e:
        print('ERROR: descarga/validación fallida; se conservan archivos anteriores. '+str(e),file=sys.stderr)
        return 1

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin','*')
        self.send_header('Cache-Control','no-store')
        super().end_headers()

def main():
    p=argparse.ArgumentParser();p.add_argument('accion',choices=['actualizar','servir']);p.add_argument('--destino',default='datos_subastas');p.add_argument('--puerto',type=int,default=8765);a=p.parse_args();dest=pathlib.Path(a.destino).resolve()
    if a.accion=='actualizar':return actualizar(dest)
    dest.mkdir(parents=True,exist_ok=True);os.chdir(dest)
    server=http.server.ThreadingHTTPServer(('0.0.0.0',a.puerto),Handler)
    print('Sirviendo archivos oficiales en puerto',a.puerto,'(no realiza actualizaciones por sí solo)');server.serve_forever()
if __name__=='__main__':sys.exit(main())
