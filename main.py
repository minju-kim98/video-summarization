import torch
from training.summary.datamodule import SummaryDataset
from transformers import ViTImageProcessor
from tqdm import tqdm
import matplotlib.pyplot as plt
import cv2
import seaborn as sns
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips

from v2021 import SummaryModel

preprocessor = ViTImageProcessor.from_pretrained(
    "google/vit-base-patch16-224", size=224, device='cuda'
)

SAMPLE_EVERY_SEC = 2

video_path = 'videos/test.mp4'

cap = cv2.VideoCapture(video_path)

n_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
fps = cap.get(cv2.CAP_PROP_FPS)

video_len = n_frames / fps

print(f'Video length {video_len:.2f} seconds!')

frames = []
last_collected = -1

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    timestamp = cap.get(cv2.CAP_PROP_POS_MSEC)
    second = timestamp // 1000

    if second % SAMPLE_EVERY_SEC == 0 and second != last_collected:
        last_collected = second
        frames.append(frame)

features = preprocessor(images=frames, return_tensors="pt")["pixel_values"]

print(features.shape)

plt.figure(figsize=(10, 10))
plt.imshow(features[0].numpy().transpose(1, 2, 0)[:, :, ::-1])

model = SummaryModel.load_from_checkpoint('summary.ckpt')
model.to('cuda')
model.eval()

features = features.to('cuda')

y_pred = []

for frame in tqdm(features):
    y_p = model(frame.unsqueeze(0))
    y_p = torch.sigmoid(y_p)

    y_pred.append(y_p.cpu().detach().numpy().squeeze())

y_pred = np.array(y_pred)

sns.displot(y_pred)

def determine_threshold(y_pred, THRESHOLD):
    total_secs = 0

    for i, y_p in enumerate(y_pred):
        if y_p >= THRESHOLD:
            total_secs += SAMPLE_EVERY_SEC
    return total_secs

THRESHOLD = 0.64
while(total_secs > 60):
    THRESHOLD -= 0.01
    total_secs = determine_threshold(y_pred, THRESHOLD)

clip = VideoFileClip(video_path)

subclips = []

for i, y_p in enumerate(y_pred):
    sec = i * SAMPLE_EVERY_SEC

    if y_p >= THRESHOLD:
        start = sec - SAMPLE_EVERY_SEC
        if start < 0:
            start = 0
        subclip = clip.subclip(start, sec)
        subclips.append(subclip)

result = concatenate_videoclips(subclips)

result.write_videofile("videos/result.mp4")