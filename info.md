for backend : 
uvicorn main:app --reload --host 0.0.0.0 --port 8000 
or 
py -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

for debug: (in venv) python debug\debug_capture.py



# data collection

data_collection/collect_sequences for data collection, run it, saves to dataset/phrases

for quick summary run export_dataset_info.py

phrases.json for phrases