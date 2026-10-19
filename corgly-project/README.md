# Corg.ly санал асуулга

Python 3.10+ шаардлагатай. Нэмэлт сан суулгахгүй.

```sh
cd corgly-project
python3 server.py
```

http://127.0.0.1:8000 хаягийг нээнэ. Зогсоох: Ctrl+C.
Дан хэрэглэгчийн сургалтын загвар. Өгөгдөл surveys.sqlite3 файлд хадгалагдана.
Нэвтрэлт, нэг хүн нэг санал, интернэтээр хуваалцах боломж энэ хувилбарт байхгүй.

Slack холболтыг сервер эхлэхээс өмнө тохируулна. Нууц хаягаа код эсвэл тайланд бүү оруул.

```sh
python3 -c 'import getpass,os,runpy; os.environ["SLACK_WEBHOOK_URL"]=getpass.getpass("Slack Webhook URL: "); runpy.run_path("server.py",run_name="__main__")'
```

Командыг ажиллуулаад “Slack Webhook URL:” асуултын дараа webhook хаягаа оруулж Enter дарна. Утга дэлгэцэд харагдахгүй. Сервер ажиллаж байвал эхлээд Ctrl+C дарж зогсооно.
API баримтжуулалтыг дагалдах documentation сайтаас үзнэ.
