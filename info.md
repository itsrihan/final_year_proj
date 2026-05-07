for backend : 
uvicorn main:app --reload --host 0.0.0.0 --port 8000 
or 
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

for debug: (in venv) python debug\debug_capture.py

for venv in linux: source ~/asl_venv/bin/activate

 export CORS_ALLOW_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,http://192.168.0.147:5173"





# data collection

data_collection/collect_sequences for data collection, run it, saves to dataset/phrases

for quick summary run export_dataset_info.py

phrases.json for phrases