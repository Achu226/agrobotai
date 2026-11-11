# 🚀 HORTICBOTAI Upgrade Guide - Maximum Accuracy Edition

This guide covers upgrading HORTICBOTAI with state-of-the-art features and GPU-accelerated training.

## 🎯 New Features Added

### 1. **Disease Severity Calculator** 
- Semantic segmentation to calculate % of leaf area infected
- Stage classification (Early/Moderate/Severe)

### 2. **Nutrient Deficiency Detection**
- N-P-K (Nitrogen, Phosphorus, Potassium) deficiency classification
- Micronutrient detection (Iron, Zinc, Magnesium)

### 3. **Weather-Based Disease Risk Forecasting**
- Real-time weather API integration
- Predictive risk models for Late Blight, Downy Mildew, etc.

### 4. **Chemical Dosage Calculator**
- Exact pesticide/fungicide mixing instructions
- Organic alternative recommendations

### 5. **Grad-CAM Visualization**
- Visual heatmaps showing which leaf areas triggered detection
- Builds farmer trust and model interpretability

### 6. **Crop Recovery Tracking**
- Multi-scan timeline to monitor treatment effectiveness
- Recovery index calculation

### 7. **Advanced Model Architecture**
- ConvNeXt-V2 / EfficientNet-V2 with attention mechanisms
- Focal Loss for hard-example mining
- Test-Time Augmentation for higher reliability

---

## 🖥️ GPU Setup (REQUIRED for Training)

### Your Hardware
- **GPU**: NVIDIA GeForce RTX 4060 (8GB VRAM) ✅
- **CUDA**: Version 13.4 ✅

### Python Version Requirement
⚠️ **IMPORTANT**: PyTorch with CUDA support requires **Python 3.10, 3.11, or 3.12** (not 3.14).

#### Option 1: Install Python 3.11 (Recommended)
```powershell
# Download Python 3.11.9 from python.org
# Install to C:\Python311
# Create new virtual environment
C:\Python311\python.exe -m venv .venv-gpu
.venv-gpu\Scripts\activate
python -m pip install --upgrade pip
```

#### Option 2: Use Conda/Miniconda
```powershell
conda create -n horticbot python=3.11
conda activate horticbot
```

### Install PyTorch with CUDA 12.1
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install -r requirements-gpu.txt
```

### Verify GPU
```powershell
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0))"
```
Expected output:
```
CUDA: True
GPU: NVIDIA GeForce RTX 4060
```

---

## 📊 Dataset Preparation

Your current dataset structure:
```
data/
├── pest/
│   ├── train/
│   │   ├── aphids/
│   │   ├── armyworm/
│   │   └── ...
│   └── test/
└── disease/
    ├── train/
    └── test/
```

### Create Stratified Train/Val/Test Split
```powershell
python scripts/prepare_dataset.py --data-dir data/pest --split 0.75 0.15 0.10
python scripts/prepare_dataset.py --data-dir data/disease --split 0.75 0.15 0.10
```

This reorganizes into:
```
data/
├── pest/
│   ├── train/ (75%)
│   ├── val/ (15%)
│   └── test/ (10%)
```

---

## 🏋️ Training - Pest Detection Model

### Quick Start (Transfer Learning)
```powershell
python train_pest.py \
    --data-dir data/pest \
    --model convnext_tiny \
    --batch-size 32 \
    --epochs 50 \
    --lr 0.001 \
    --device cuda \
    --output-dir models/pest_convnext
```

### Advanced Training (Maximum Accuracy)
```powershell
python train_pest.py \
    --data-dir data/pest \
    --model convnext_small \
    --batch-size 24 \
    --epochs 100 \
    --lr 0.001 \
    --optimizer adamw \
    --scheduler cosine \
    --augmentation advanced \
    --loss focal \
    --focal-alpha 0.25 \
    --focal-gamma 2.0 \
    --mixup 0.2 \
    --cutmix 0.2 \
    --label-smoothing 0.1 \
    --test-time-aug \
    --device cuda \
    --output-dir models/pest_convnext_advanced
```

### Training Options

#### Model Architecture (`--model`)
- `efficientnet_v2_s` - Fast, 84% ImageNet accuracy
- `convnext_tiny` - **Recommended**, 82% ImageNet, best speed/accuracy tradeoff
- `convnext_small` - 83% ImageNet, higher capacity
- `swin_v2_t` - Vision Transformer, 82% ImageNet, excellent for fine details

#### Augmentation (`--augmentation`)
- `basic` - Resize, flip, rotate
- `medium` - Basic + color jitter, blur
- `advanced` - Medium + CLAHE, elastic transform, MixUp/CutMix

#### Loss Function (`--loss`)
- `crossentropy` - Standard classification loss
- `focal` - **Recommended**, focuses on hard examples
- `label_smooth` - Prevents overconfidence

---

## 🏋️ Training - Disease Detection Model

```powershell
python train_disease.py \
    --data-dir data/disease \
    --model convnext_tiny \
    --batch-size 32 \
    --epochs 80 \
    --lr 0.001 \
    --augmentation advanced \
    --loss focal \
    --device cuda \
    --output-dir models/disease_convnext
```

---

## 🧪 Training - Nutrient Deficiency Model

First, collect/organize nutrient deficiency images:
```
data/nutrients/
├── train/
│   ├── healthy/
│   ├── nitrogen_deficiency/
│   ├── phosphorus_deficiency/
│   ├── potassium_deficiency/
│   ├── iron_deficiency/
│   └── zinc_deficiency/
└── test/
```

```powershell
python train_nutrients.py \
    --data-dir data/nutrients \
    --model convnext_tiny \
    --epochs 60 \
    --device cuda \
    --output-dir models/nutrient_convnext
```

---

## 🎯 Expected Training Performance

### RTX 4060 (8GB) Training Speed
| Model | Batch Size | Images/Second | Epoch Time (10K images) |
|-------|-----------|---------------|------------------------|
| ConvNeXt-Tiny | 32 | ~180 | 55 seconds |
| ConvNeXt-Small | 24 | ~140 | 71 seconds |
| EfficientNet-V2-S | 32 | ~200 | 50 seconds |

### Expected Accuracy (86K Dataset)
| Model | Baseline | With Advanced Aug | With Focal Loss + TTA |
|-------|----------|------------------|----------------------|
| EfficientNet-B0 | 92-94% | 94-96% | 95-97% |
| ConvNeXt-Tiny | 94-96% | 96-97% | **97-98%** |
| ConvNeXt-Small | 95-97% | 97-98% | **98-99%** |

---

## 🔬 Model Evaluation

```powershell
# Evaluate on test set
python evaluate.py \
    --model models/pest_convnext/best_model.pth \
    --data-dir data/pest/test \
    --output-dir outputs/eval_pest

# Generate confusion matrix, per-class accuracy, Grad-CAM visualizations
```

---

## 🚀 Deploy Updated Models

### Update Model Paths in .env
```env
PEST_MODEL_PATH=models/pest_convnext/best_model.pth
DISEASE_MODEL_PATH=models/disease_convnext/best_model.pth
NUTRIENT_MODEL_PATH=models/nutrient_convnext/best_model.pth
OPENAI_API_KEY=your-key-here
WEATHER_API_KEY=your-weather-api-key
```

### Run Application
```powershell
streamlit run app.py
```

---

## 📈 Training Tips for Maximum Accuracy

1. **Start Small, Scale Up**: Train ConvNeXt-Tiny first (fast iterations), then move to ConvNeXt-Small for final deployment
2. **Monitor Validation Loss**: If it stops improving after 20 epochs, reduce learning rate by 10x
3. **Use Early Stopping**: Stop training if validation accuracy doesn't improve for 10 epochs
4. **Test-Time Augmentation**: Always enable for production inference (+2-3% accuracy)
5. **Ensemble Models**: Train 3 different architectures (ConvNeXt, EfficientNet-V2, Swin-V2) and average predictions for ultimate accuracy

---

## 🐛 Troubleshooting

### CUDA Out of Memory
- Reduce `--batch-size` (try 16 or 8)
- Use `--mixed-precision` for automatic FP16 training
- Use smaller model (convnext_tiny instead of small)

### Training Too Slow
- Increase `--num-workers` for data loading (try 4 or 8)
- Enable `--pin-memory`
- Check GPU utilization with `nvidia-smi -l 1`

### Accuracy Not Improving
- Check class imbalance (use `--weighted-loss`)
- Verify augmentation isn't too aggressive
- Try different learning rate (0.0001 - 0.01)
- Ensure data split is stratified

---

## 📝 Next Steps

1. ✅ Install Python 3.11 and PyTorch with CUDA
2. ✅ Verify GPU is working
3. ✅ Prepare dataset with stratified splits
4. ✅ Train pest model with ConvNeXt-Tiny
5. ✅ Train disease model with ConvNeXt-Tiny
6. ✅ Evaluate models and compare accuracy
7. ✅ Deploy to Streamlit app
8. ✅ Train nutrient deficiency model (if dataset available)
9. ✅ Add weather forecasting integration
10. ✅ Implement Grad-CAM visualization

---

**Your model will be OP! 🚀**
