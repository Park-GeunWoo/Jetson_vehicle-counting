from ultralytics import YOLO
import torch
model = YOLO('yolov8n.pt')
print(torch.cuda.is_available())
#model.export(format="engine", device='dla:0', half=True)
#model = YOLO('yolov8n.engine',task='detect')