# 🚀 99% Accuracy GPU Training Plan

**Date**: 2026-09-13  
**GPU**: NVIDIA GeForce RTX 4060 (8GB VRAM)  
**Status**: Ready to Start

---

## 📊 Dataset Summary

### **Pest Classification**
- **Train**: 2,158 images (9 classes)
- **Val**: 459 images
- **Test**: 321 images
- **Total**: 2,938 images
- **Classes**: Aphids, Armyworm, Beetle, Bollworm, Grasshopper, Mites, Mosquito, Sawfly, Stem Borer

### **Disease Classification**
- **Train**: 12,963 images (15 classes)
- **Val**: 2,585 images
- **Test**: 1,746 images
- **Total**: 17,294 images
- **Classes**: Tomato Early/Late Blight, Bacterial Spot, Leaf Mold, Septoria, Yellow Leaf Curl, Target Spot, Mosaic Virus, Spider Mites, Potato Early/Late Blight, Pepper Bacterial Spot, Healthy variants

---

## 🧠 Training Configuration

### **Model Architecture**
- **Primary**: ConvNeXt-Tiny (Modern CNN, fast + accurate)
- **Alternative**: EfficientNet-V2-S, ConvNeXt-Small, Swin-V2-Tiny

### **Optimization Strategy for 99% Accuracy**
1. ✅ **Pretrained ImageNet weights** (Transfer learning)
2. ✅ **Focal Loss** with γ=2.0 (Hard example mining)
3. ✅ **Label Smoothing** (0.1 - reduces overconfidence)
4. ✅ **Strong Data Augmentation**:
   - Random crops, flips, rotation
   - Color jitter, random erasing
5. ✅ **AdamW Optimizer** with weight decay 1e-2
6. ✅ **Cosine Annealing LR** schedule with warm restarts
7. ✅ **Mixed Precision (FP16)** for 2x speedup on RTX 4060
8. ✅ **Gradient Clipping** (max_norm=1.0)
9. ✅ **Dropout** layers (0.3-0.4)

### **Hyperparameters**
- **Batch Size**: 32 (optimized for 8GB VRAM)
- **Learning Rate**: 3e-4 (AdamW default)
- **Image Size**: 224×224
- **Epochs**: 25 (Pest), 40 (Disease - larger dataset)

---

## ⏱️ Estimated Training Time

### **RTX 4060 Performance Estimate**
- **Speed**: ~150-200 images/second (FP16 mixed precision)
- **Batch processing**: 32 images per forward pass

### **Pest Model Training**
- Total training images per epoch: 2,158
- Epochs: 25
- **Total images processed**: 53,950
- **Estimated time**: **4-6 minutes** ⚡

### **Disease Model Training**
- Total training images per epoch: 12,963
- Epochs: 40
- **Total images processed**: 518,520
- **Estimated time**: **45-60 minutes** 🕐

### **Total Training Time: ~50-70 minutes for both models**

---

## 🎯 Expected Accuracy Results

### **Pest Classification**
- **Current baseline**: ~85-90%
- **After GPU training**: **95-97%** (small dataset, 9 classes)
- **To reach 99%**: Need more pest images (recommend 500+ per class)

### **Disease Classification**
- **Current baseline**: ~80-85%
- **After GPU training**: **97-99%** ✅ (large dataset, 17K images)
- **Best case**: 99%+ on common diseases like Early Blight, Late Blight

---

## 📋 Training Commands

### **Step 1: Train Pest Model**
```bash
python scripts/train_gpu_fast.py \
  --data-dir data/pest \
  --task-name pest \
  --model convnext_tiny \
  --epochs 25 \
  --batch-size 32 \
  --lr 3e-4 \
  --output-dir models
```

**Progress Display**:
```
Epoch [ 5/25] █████████████████████░░░░ [2158/2158 img] Loss: 0.1234 | Acc:  94.50% | 180.5 img/s | ETA:    0s
   Validation: Loss: 0.1456 | Acc:  96.25% | Best:  96.25% | Time: 15.3s 🌟 NEW BEST!
```

---

### **Step 2: Train Disease Model**
```bash
python scripts/train_gpu_fast.py \
  --data-dir data/disease \
  --task-name disease \
  --model convnext_tiny \
  --epochs 40 \
  --batch-size 32 \
  --lr 3e-4 \
  --output-dir models
```

**Progress Display**:
```
Epoch [10/40] ██████████████░░░░░░░░░░░ [12963/12963 img] Loss: 0.0823 | Acc:  97.80% | 175.2 img/s | ETA:    0s
   Validation: Loss: 0.0912 | Acc:  98.35% | Best:  98.35% | Time: 72.1s 🌟 NEW BEST!
```

---

## 📈 Live Progress Features

The new training script shows:
- ✅ **Progress bar** with visual █ indicator
- ✅ **Image counter**: [Done / Total / Remaining]
- ✅ **Real-time accuracy** and loss
- ✅ **Processing speed**: images per second
- ✅ **ETA**: Estimated seconds remaining for current epoch
- ✅ **Best model tracking**: Automatically saves when validation improves
- ✅ **Total time**: Summary at end

---

## 💾 Output Files

After training completes:

```
models/
├── pest_model.pt           # Best pest classifier checkpoint
├── pest_classes.json       # Class mapping + accuracy
├── disease_model.pt        # Best disease classifier checkpoint
└── disease_classes.json    # Class mapping + accuracy
```

Each `.pt` file contains:
- Model weights (state_dict)
- Best validation accuracy
- Class names and indices
- Model architecture name
- Image size used

---

## 🚀 How to Start Training Now

### **Option A: Train Both Models Sequentially**
```bash
# Train pest first (fast, 5 minutes)
python scripts/train_gpu_fast.py --data-dir data/pest --task-name pest --model convnext_tiny --epochs 25

# Then train disease (slower, 50 minutes)
python scripts/train_gpu_fast.py --data-dir data/disease --task-name disease --model convnext_tiny --epochs 40
```

### **Option B: Train Only Disease (Most Impact)**
```bash
# Focus on disease model - largest dataset, highest accuracy potential
python scripts/train_gpu_fast.py --data-dir data/disease --task-name disease --model convnext_tiny --epochs 40
```

---

## 🎯 Next Steps After Training

1. ✅ Models will be saved to `models/pest_model.pt` and `models/disease_model.pt`
2. Update `.env` to point to new models:
   ```env
   PEST_MODEL_PATH=models/pest_model.pt
   DISEASE_MODEL_PATH=models/disease_model.pt
   ```
3. Restart the app with `start.bat`
4. Test with new leaf images - should see **97-99% confidence** on clear images!

---

## 📊 Monitoring During Training

Watch for:
- **Training accuracy climbing**: 70% → 90% → 97%+
- **Validation accuracy**: Should follow training (gap < 5%)
- **Loss decreasing**: Should drop below 0.15 by end
- **"🌟 NEW BEST!" markers**: Means model is improving
- **Final test accuracy**: Real-world performance metric

---

## ⚡ Performance Tips

✅ **Already optimized**:
- FP16 mixed precision (2x faster)
- Efficient batch size (32 images)
- Pin memory enabled
- 4 dataloader workers

🚀 **To speed up further** (if needed):
- Increase `--batch-size 64` (if VRAM allows)
- Reduce `--image-size 192` (slightly less accurate)
- Use `--model efficientnet_v2_s` (faster inference)

---

## 🏆 Success Criteria

### **Pest Model**
- ✅ Validation accuracy ≥ 95%
- ✅ Test accuracy ≥ 93%

### **Disease Model**
- ✅ Validation accuracy ≥ 98%
- ✅ Test accuracy ≥ 97%

---

**Ready to achieve 99% accuracy? Run the commands above!** 🚀
