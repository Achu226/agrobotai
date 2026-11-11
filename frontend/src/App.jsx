import React, { useState, useEffect, useRef, Component } from 'react';
import AdminPanel from './AdminPanel';
import FarmerPanel from './FarmerPanel';
import {
  Leaf,
  Bug,
  FlaskConical,
  FileText,
  Download,
  Upload,
  Camera,
  Key,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Sparkles,
  Droplets,
  Calendar,
  Clock,
  RefreshCw,
  Eye,
  Sliders,
  Calculator,
  CloudSun,
  MessageSquare,
  Send,
  Globe,
  Activity,
  MapPin,
  Thermometer,
  Wind,
  Percent,
  Bot,
  User,
  Target,
  Zap,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  ScanEye,
  Trash2
} from 'lucide-react';

// Error Boundary Component
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('React Error Boundary caught:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          maxWidth: '800px',
          margin: '40px auto',
          background: '#fee2e2',
          border: '2px solid #dc2626',
          borderRadius: '12px',
          fontFamily: 'system-ui, -apple-system, sans-serif'
        }}>
          <h1 style={{ color: '#991b1b', marginBottom: '16px', fontSize: '24px' }}>
            ⚠️ Rendering Error Detected
          </h1>
          <p style={{ color: '#7f1d1d', marginBottom: '16px', fontSize: '16px' }}>
            The diagnostic output failed to render. This usually happens when the backend response is missing required fields.
          </p>
          <details style={{
            background: 'white',
            padding: '16px',
            borderRadius: '8px',
            border: '1px solid #fca5a5',
            marginBottom: '16px'
          }}>
            <summary style={{ cursor: 'pointer', fontWeight: '600', color: '#991b1b', marginBottom: '8px' }}>
              Error Details
            </summary>
            <pre style={{
              fontSize: '13px',
              color: '#7f1d1d',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              margin: '8px 0 0 0'
            }}>
              {this.state.error?.toString()}
              {this.state.errorInfo?.componentStack}
            </pre>
          </details>
          <button
            onClick={() => window.location.reload()}
            style={{
              background: '#dc2626',
              color: 'white',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '16px',
              fontWeight: '600'
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

// Same origin when served by FastAPI (works from a phone via the LAN IP too);
// the Vite dev server (port 5173) talks to the backend on :8000.
const API_BASE = import.meta.env.VITE_API_BASE
  || (window.location.port === '5173' ? `${window.location.protocol}//${window.location.hostname}:8000` : window.location.origin);

const scoreColor = (score) => (score == null ? '#64748b' : score >= 80 ? '#059669' : score >= 60 ? '#d97706' : '#dc2626');

const CROP_ICONS = {
  "Auto-Detect Plant Species": "🔍",
  "Tomato": "🍅",
  "Potato": "🥔",
  "Bell Pepper": "🫑",
  "Green Chilli": "🌶️",
  "Brinjal": "🍆",
  "Corn (Maize)": "🌽",
  "Rice (Paddy)": "🌾",
  "Wheat": "🌾",
  "Cotton": "☁️",
  "Sugarcane": "🎋",
  "Soybean": "🫘",
};

const LANG_LOCALE_MAP = {
  ta: 'ta-IN',
  hi: 'hi-IN',
  en: 'en-IN',
  te: 'te-IN',
  kn: 'kn-IN',
  ml: 'ml-IN',
  mr: 'mr-IN',
  bn: 'bn-IN',
  pa: 'pa-IN',
  gu: 'gu-IN'
};

const GREETING_MESSAGES = {
  ta: 'வணக்கம்! நான் உங்கள் AI வேளாண்மை ஆலோசகர். பயிர் நோய், பூச்சி தாக்குதல் மற்றும் இயற்கை மருந்துகள் பற்றி எந்த கேள்வியும் கேட்கலாம்.',
  hi: 'नमस्ते! मैं आपका AI कृषि सलाहकार हूँ। फसल रोग, कीट प्रबंधन और जैविक उपचार के बारे में कोई भी प्रश्न पूछें।',
  en: 'Hello! I am your AI Agronomist Advisor. Ask me anything about crop diseases, pest control, or organic treatments.',
  te: 'నమస్కారం! నేను మీ AI వ్యవసాయ సలహాదారుని. పంట తెగుళ్లు, పురుగుల నివారణ గురించి అడగండి.',
  kn: 'ನಮಸ್ಕಾರ! ನಾನು ನಿಮ್ಮ AI ಕೃಷಿ ಸಲಹೆಗಾರ. ಬೆಳೆ ರೋಗಗಳು ಮತ್ತು ಕೀಟ ನಿಯಂತ್ರಣದ ಬಗ್ಗೆ ಕೇಳಿ.',
  ml: 'നമസ്കാരം! ഞാൻ നിങ്ങളുടെ AI കാർഷിക ഉപദേശകനാണ്. വിള രോഗങ്ങളെയും കീടങ്ങളെയും കുറിച്ച് ചോദിക്കാം.',
  mr: 'नमस्कार! मी तुमचा AI कृषी सल्लागार आहे. पीक रोग, कीड नियंत्रण आणि जैविक उपचारांबद्दल विचारा.',
  bn: 'নমস্কার! আমি আপনার AI কৃষি পরামর্শদাতা। ফসলের রোগ, কীটপতঙ্গ দমন এবং জৈব প্রতিকার সম্পর্কে জিজ্ঞাসা করুন।',
  pa: 'ਸਤਿ ਸ਼੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡਾ AI ਖੇਤੀਬਾੜੀ ਸਲਾਹਕਾਰ ਹਾਂ। ਫਸਲਾਂ ਦੇ ਰੋਗਾਂ ਅਤੇ ਕੀੜਿਆਂ ਦੇ ਹੱਲ ਬਾਰੇ ਪੁੱਛੋ।',
  gu: 'નમસ્તે! હું તમારો AI કૃષિ સલાહકાર છું. પાકના રોગો અને જંતુ નિયંત્રણ વિશે પ્રશ્નો પૂછો।'
};

const QUICK_QUESTION_CHIPS = {
  ta: [
    { label: '💊 சிறந்த சிகிச்சை என்ன?', query: 'இந்த நோய்க்கான சிறந்த சிகிச்சை என்ன?' },
    { label: '🌿 இயற்கை மருந்து தயாரிப்பு', query: 'இயற்கை பூச்சி மருந்து தயாரிப்பது எப்படி?' },
    { label: '💧 பாசன வழிகாட்டல்', query: 'தண்ணீர் பாசனம் எப்போது செய்ய வேண்டும்?' },
    { label: '🧪 NPK உர அளவு', query: 'உர நிர்வாகம் மற்றும் NPK அளவு பற்றி சொல்லுங்கள்' }
  ],
  hi: [
    { label: '💊 सबसे अच्छा इलाज क्या है?', query: 'इस बीमारी के लिए सबसे अच्छी दवा कौन सी है?' },
    { label: '🌿 जैविक कीटनाशक', query: 'जैविक कीटनाशक कैसे तैयार करें?' },
    { label: '💧 सिंचाई सलाह', query: 'सिंचाई का सही समय और तरीका क्या है?' },
    { label: '🧪 खाद एवं NPK मात्रा', query: 'उर्वरक प्रबंधन और NPK की सही मात्रा बताएं' }
  ],
  en: [
    { label: '💊 Recommended Treatment', query: 'What is the best treatment for this issue?' },
    { label: '🌿 Organic Bio-Control', query: 'How to prepare organic bio-pesticides?' },
    { label: '💧 Irrigation Guide', query: 'What is the ideal watering schedule?' },
    { label: '🧪 Fertilizer & NPK', query: 'Explain fertilizer management and NPK ratio' }
  ],
  te: [
    { label: '💊 ఉత్తమ నివారణ ఏమిటి?', query: 'ఈ తెగులుకు ఉత్తమ నివారణ ఏమిటి?' },
    { label: '🌿 సేంద్రీయ మందులు', query: 'సేంద్రీయ పురుగుల మందు ఎలా తయారు చేయాలి?' },
    { label: '💧 నీటి పారుదల', query: 'నీటి పారుదల ఎప్పుడు చేయాలి?' },
    { label: '🧪 ఎరువుల యాజమాన్యం', query: 'ఎరువుల యాజమాన్యం మరియు NPK మోతాదు తెలపండి' }
  ],
  kn: [
    { label: '💊 ಉತ್ತಮ ಚಿಕಿತ್ಸೆ ಏನು?', query: 'ಈ ರೋಗಕ್ಕೆ ಉತ್ತಮ ಚಿಕಿತ್ಸೆ ಏನು?' },
    { label: '🌿 ಸಾವಯವ ಔಷಧಿ', query: 'ಸಾವಯವ ಕೀಟನಾಶಕ ತಯಾರಿಸುವುದು ಹೇಗೆ?' },
    { label: '💧 ನೀರಾವರಿ ಮಾರ್ಗದರ್ಶನ', query: 'ನೀರಾವರಿ ಯಾವಾಗ ಮಾಡಬೇಕು?' },
    { label: '🧪 ರಸಗೊಬ್ಬರ ನಿರ್ವಹಣೆ', query: 'ರಸಗೊಬ್ಬರ ಮತ್ತು NPK ಪ್ರಮಾಣ ತಿಳಿಸಿ' }
  ],
  ml: [
    { label: '💊 മികച്ച ചികിത്സ എന്താണ്?', query: 'ഈ രോഗത്തിനുള്ള മികച്ച ചികിത്സ എന്താണ്?' },
    { label: '🌿 ജൈവ കീടനാശിനി', query: 'ജൈവ കീടനാശിനി എങ്ങനെ തയ്യാറാക്കാം?' },
    { label: '💧 നനയ്ക്കൽ സമയം', query: 'നനയ്ക്കൽ എപ്പോൾ നടത്തണം?' },
    { label: '🧪 വളപ്രയോഗം', query: 'വളപ്രയോഗവും NPK അളവും വ്യക്തമാക്കുക' }
  ]
};

// Auto-detect script language directly from Unicode characters in text
const detectTextLanguage = (text, fallbackLang = 'ta') => {
  if (!text) return fallbackLang;
  const counts = {
    ta: (text.match(/[஀-௿]/g) || []).length,
    hi: (text.match(/[ऀ-ॿ]/g) || []).length,
    te: (text.match(/[ఀ-౿]/g) || []).length,
    kn: (text.match(/[ಀ-೿]/g) || []).length,
    ml: (text.match(/[ഀ-ൿ]/g) || []).length,
    bn: (text.match(/[ঀ-৿]/g) || []).length,
    gu: (text.match(/[઀-૿]/g) || []).length,
    pa: (text.match(/[਀-੿]/g) || []).length,
  };
  let maxLang = fallbackLang;
  let maxCount = 0;
  for (const [lang, count] of Object.entries(counts)) {
    if (count > maxCount) {
      maxCount = count;
      maxLang = lang;
    }
  }
  if (maxCount >= 2) return maxLang;
  const latinCount = (text.match(/[a-zA-Z]/g) || []).length;
  if (latinCount > 5 && maxCount === 0) return 'en';
  return fallbackLang;
};

function AppContent() {
  const [crops, setCrops] = useState([]);
  const [selectedCrop, setSelectedCrop] = useState('Auto-Detect Plant Species');
  const [criVariant, setCriVariant] = useState('CRI1');
  const [apiKey, setApiKey] = useState('');

  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const [activeTab, setActiveTab] = useState('emergency');
  const [cameraActive, setCameraActive] = useState(false);

  // Scan history (persisted server-side in outputs/scans.db)
  const [scanHistory, setScanHistory] = useState([]);

  // Interactive Dosage Calculator state
  const [fieldAcreage, setFieldAcreage] = useState(1.0);
  const [tankCapacity, setTankCapacity] = useState(15.0);
  const [dosageTarget, setDosageTarget] = useState('Early Blight');
  const [dosageMode, setDosageMode] = useState('both');
  const [customDosage, setCustomDosage] = useState(null);
  const [loadingDosage, setLoadingDosage] = useState(false);

  // Weather & Outbreak Risk state
  const [weatherLocation, setWeatherLocation] = useState('Salem, Tamil Nadu');
  const [weatherData, setWeatherData] = useState(null);
  const [loadingWeather, setLoadingWeather] = useState(false);

  // Multilingual Chatbot state
  const [languages, setLanguages] = useState([]);
  const [selectedLang, setSelectedLang] = useState('ta');
  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'bot',
      text: 'வணக்கம்! நான் உங்கள் AI வேளாண்மை ஆலோசகர். பயிர் நோய், பூச்சி தாக்குதல் மற்றும் இயற்கை மருந்துகள் பற்றி எந்த கேள்வியும் கேட்கலாம்.',
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [loadingChat, setLoadingChat] = useState(false);

  // NLP Voice STT & TTS state
  const [isListening, setIsListening] = useState(false);
  const [speakingIndex, setSpeakingIndex] = useState(null);
  const [loadingAudioIndex, setLoadingAudioIndex] = useState(null);
  const [elevenLabsKey, setElevenLabsKey] = useState('');
  const [elevenLabsVoice, setElevenLabsVoice] = useState('21m00Tcm4TlvDq8ikWAM');
  const recognitionRef = useRef(null);
  const audioPlayerRef = useRef(null);

  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  const chatBottomRef = useRef(null);

  // Initial load
  useEffect(() => {
    // Fetch crops
    fetch(`${API_BASE}/api/crops`)
      .then(res => res.json())
      .then(data => {
        if (data.crops) setCrops(data.crops);
      })
      .catch(err => console.warn('Crops fetch error:', err));

    // Fetch supported languages
    fetch(`${API_BASE}/api/languages`)
      .then(res => res.json())
      .then(data => {
        if (data.languages) {
          // Ensure languages is always an array
          const languagesArray = Array.isArray(data.languages) ? data.languages : [];
          setLanguages(languagesArray);
        }
      })
      .catch(err => console.warn('Languages fetch error:', err));

    // Fetch initial weather risk
    fetchWeatherRisk('Salem, Tamil Nadu', 'Tomato', null);

    loadHistory();
  }, []);

  const loadHistory = () => {
    fetch(`${API_BASE}/api/history?limit=20`)
      .then(res => res.json())
      .then(data => setScanHistory(Array.isArray(data.scans) ? data.scans : []))
      .catch(err => console.warn('History fetch error:', err));
  };

  const deleteHistoryScan = async (scanId) => {
    try {
      const res = await fetch(`${API_BASE}/api/history/${scanId}`, { method: 'DELETE' });
      if (res.ok) setScanHistory(prev => prev.filter(s => s.id !== scanId));
    } catch (err) {
      console.warn('History delete error:', err);
    }
  };

  // Scroll chat to bottom on new messages
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Clean up object URLs on component unmount
  useEffect(() => {
    return () => {
      if (imagePreview && imagePreview.startsWith('blob:')) {
        URL.revokeObjectURL(imagePreview);
      }
    };
  }, [imagePreview]);

  const handleFileChange = (file) => {
    if (!file) return;

    // Clean up previous preview URL if it exists
    if (imagePreview && imagePreview.startsWith('blob:')) {
      URL.revokeObjectURL(imagePreview);
    }

    setImageFile(file);

    // Create object URL instead of data URL for better memory management
    const objectUrl = URL.createObjectURL(file);
    setImagePreview(objectUrl);

    setResult(null);
    setError(null);
    setCustomDosage(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const startCamera = async () => {
    setCameraActive(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      alert("Camera access denied or unavailable.");
      setCameraActive(false);
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth || 640;
    canvas.height = videoRef.current.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      const file = new File([blob], 'camera_capture.jpg', { type: 'image/jpeg' });
      handleFileChange(file);
      stopCamera();
    }, 'image/jpeg');
  };

  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const stream = videoRef.current.srcObject;
      stream.getTracks().forEach(track => track.stop());
    }
    setCameraActive(false);
  };

  const runDiagnosis = async () => {
    if (!imageFile) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setCustomDosage(null);

    const formData = new FormData();
    formData.append('file', imageFile);
    formData.append('crop', selectedCrop);
    formData.append('cri_variant', criVariant);
    formData.append('api_key', apiKey);

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Analysis request failed.');
      }

      const data = await res.json();
      setResult(data);
      loadHistory();

      // Auto-populate dosage target from diagnosis
      const detectedTarget = data.disease?.identified !== 'Healthy' && data.disease?.identified !== 'No Disease' && !data.disease?.is_healthy_class
        ? data.disease?.identified
        : (data.pest?.pest_detected && data.pest?.identified !== 'No Pest' ? data.pest?.identified : (data.dosage_recommendation?.chemical?.target || 'Early Blight'));

      setDosageTarget(detectedTarget);

      // Auto-trigger weather risk for detected crop & disease
      fetchWeatherRisk(weatherLocation, data.crop || selectedCrop, data.disease?.identified);

      // Add a greeting update in chat
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: `🔍 பகுப்பாய்வு முடிந்தது! பயிர்: ${data.crop || selectedCrop} | நிலை: ${data.overall?.overall_status || 'Analyzed'}. இந்த அறிக்கை தொடர்பாக உங்களுக்கு ஏதேனும் சந்தேகங்கள் இருந்தால் கேளுங்கள்.`,
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);

    } catch (err) {
      setError(err.message || 'Failed to connect to AI Diagnostic server.');
    } finally {
      setLoading(false);
    }
  };

  const calculateDynamicDosage = async (target, acres, tank, mode) => {
    setLoadingDosage(true);
    try {
      const res = await fetch(`${API_BASE}/api/dosage/calculate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: target || dosageTarget,
          field_size_acres: parseFloat(acres || fieldAcreage),
          tank_capacity_liters: parseFloat(tank || tankCapacity),
          preferred_mode: mode || dosageMode
        })
      });
      if (res.ok) {
        const data = await res.json();
        setCustomDosage(data);
      }
    } catch (err) {
      console.error('Dosage calculation error:', err);
    } finally {
      setLoadingDosage(false);
    }
  };

  const fetchWeatherRisk = async (location, crop, disease) => {
    setLoadingWeather(true);
    try {
      const res = await fetch(`${API_BASE}/api/weather/risk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location: location || weatherLocation,
          crop: crop || (result?.crop || 'Tomato'),
          detected_disease: disease || result?.disease?.identified || null
        })
      });
      if (res.ok) {
        const data = await res.json();
        setWeatherData(data);
      }
    } catch (err) {
      console.error('Weather risk error:', err);
    } finally {
      setLoadingWeather(false);
    }
  };

  const handleSendChat = async (overrideText) => {
    const textToSend = overrideText || chatInput;
    if (!textToSend.trim() || loadingChat) return;

    const userMsg = {
      sender: 'user',
      text: textToSend,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    setChatMessages(prev => [...prev, userMsg]);
    setChatInput('');
    setLoadingChat(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: textToSend,
          language: selectedLang,
          context: result || null,
          api_key: apiKey || null
        })
      });

      if (res.ok) {
        const data = await res.json();
        const botMsg = {
          sender: 'bot',
          text: data.answer || 'பதில் பெறப்படவில்லை.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        };
        setChatMessages(prev => [...prev, botMsg]);
      } else {
        throw new Error('Chat API returned error');
      }
    } catch (err) {
      setChatMessages(prev => [
        ...prev,
        {
          sender: 'bot',
          text: '⚠️ தகவல் பெற முடியவில்லை. இணைய இணைப்பை சரிபார்க்கவும்.',
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }
      ]);
    } finally {
      setLoadingChat(false);
    }
  };

  // Stop speech when language changes or unmounts
  useEffect(() => {
    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          // ignore
        }
      }
    };
  }, [selectedLang]);

  // NLP Voice Input: Speech-to-Text (STT) via Web Speech API
  const toggleListening = () => {
    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {
          console.warn('Recognition stop error:', e);
        }
      }
      setIsListening(false);
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, or a Web Speech-compatible browser.');
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.lang = LANG_LOCALE_MAP[selectedLang] || 'ta-IN';

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript;
        if (transcript) {
          setChatInput(prev => (prev ? `${prev} ${transcript}` : transcript));
        }
      };

      recognition.onerror = (event) => {
        console.warn('Speech recognition error:', event?.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Speech recognition start failed:', err);
      setIsListening(false);
    }
  };

  const handleLanguageChange = (newLang) => {
    setSelectedLang(newLang);
    // If only default welcome greeting is in chat, update it to the new language greeting
    setChatMessages(prev => {
      if (prev.length === 1 && prev[0].sender === 'bot') {
        return [{
          sender: 'bot',
          text: GREETING_MESSAGES[newLang] || GREETING_MESSAGES['ta'],
          time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        }];
      }
      return prev;
    });
  };

  // NLP Voice Output: High-Fidelity Indic Speech Synthesis (Microsoft Edge Neural TTS / ElevenLabs v2 / gTTS / Browser SpeechSynthesis)
  const speakText = async (text, index) => {
    // If clicking on currently playing message, stop it
    if (speakingIndex === index) {
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
        audioPlayerRef.current = null;
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setSpeakingIndex(null);
      setLoadingAudioIndex(null);
      return;
    }

    // Stop any existing playback
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    setSpeakingIndex(null);
    setLoadingAudioIndex(index);

    // Clean formatting markers, markdown, URLs for smooth acoustic flow
    const cleanText = text
      .replace(/[*#_`~[\]()]/g, ' ')
      .replace(/https?:\/\/\S+/g, '')
      .replace(/^\s*\d+\.\s*/gm, '')
      .replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, '')
      .trim();

    if (!cleanText) {
      setLoadingAudioIndex(null);
      return;
    }

    // Detect actual script language from the text itself
    const effectiveLang = detectTextLanguage(cleanText, selectedLang || 'ta');

    // 1. Try Server-Side High-Fidelity Audio Synthesis (Edge-TTS / ElevenLabs / gTTS)
    try {
      const response = await fetch(`${API_BASE}/api/tts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: cleanText,
          language: effectiveLang,
          voice_id: elevenLabsVoice || '21m00Tcm4TlvDq8ikWAM',
          api_key: elevenLabsKey || null
        })
      });

      if (response.ok) {
        const audioBlob = await response.blob();
        if (audioBlob && audioBlob.size > 100) {
          const audioUrl = URL.createObjectURL(audioBlob);
          const audio = new Audio(audioUrl);
          audioPlayerRef.current = audio;

          audio.onplay = () => {
            setLoadingAudioIndex(null);
            setSpeakingIndex(index);
          };

          audio.onended = () => {
            setSpeakingIndex(null);
            setLoadingAudioIndex(null);
            audioPlayerRef.current = null;
            URL.revokeObjectURL(audioUrl);
          };

          audio.onerror = (e) => {
            console.warn('Audio streaming playback error, attempting browser SpeechSynthesis fallback:', e);
            setLoadingAudioIndex(null);
            fallbackSpeechSynthesis(cleanText, index, effectiveLang);
          };

          await audio.play();
          return;
        }
      }
    } catch (err) {
      console.warn('Server TTS failed, attempting browser SpeechSynthesis fallback:', err);
    } finally {
      setLoadingAudioIndex(null);
    }

    // 2. Fallback to client-side browser SpeechSynthesis
    fallbackSpeechSynthesis(cleanText, index, effectiveLang);
  };

  const fallbackSpeechSynthesis = (cleanText, index, effectiveLang) => {
    if (!window.speechSynthesis) {
      setSpeakingIndex(null);
      setLoadingAudioIndex(null);
      return;
    }

    const langCode = effectiveLang || selectedLang || 'ta';
    const targetLocale = LANG_LOCALE_MAP[langCode] || 'ta-IN';
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = targetLocale;
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const voice = voices.find(v => v.lang.toLowerCase() === targetLocale.toLowerCase() || v.lang.toLowerCase().startsWith(langCode));
    if (voice) {
      utterance.voice = voice;
    }

    setSpeakingIndex(index);

    utterance.onend = () => {
      setSpeakingIndex(null);
      setLoadingAudioIndex(null);
    };

    utterance.onerror = () => {
      setSpeakingIndex(null);
      setLoadingAudioIndex(null);
    };

    window.speechSynthesis.speak(utterance);
  };

  const downloadReport = async (format) => {
    if (!result) return;
    try {
      const res = await fetch(`${API_BASE}/api/report/${format}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(result),
      });

      if (!res.ok) throw new Error('Report download failed');

      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'docx' ? 'docx' : format === 'pdf' ? 'pdf' : 'txt';
      a.download = `${result.crop || selectedCrop}_Health_Report.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert(`Could not download ${format.toUpperCase()} report: ${err.message}`);
    }
  };

  const getStatusBadgeClass = (statusStr) => {
    const text = String(statusStr || '').toUpperCase();
    if (text.includes('HEALTHY') || text.includes('OPTIMAL') || text.includes('NO VISIBLE') || text.includes('NO PEST') || text.includes('CLEAN')) return 'pill-ok';
    if (text.includes('SEVERE') || text.includes('CRITICAL') || text.includes('FAILED') || text.includes('INFESTATION') || text.includes('DETECTED — HIGH')) return 'pill-bad';
    return 'pill-warn';
  };

  const renderAdviceList = (items, emptyText = "No items listed.") => {
    // Ensure items is always an array
    const itemsArray = Array.isArray(items) ? items : (items ? [items] : []);
    if (itemsArray.length === 0) return <p style={{ color: '#94a3b8', fontStyle: 'italic' }}>{emptyText}</p>;
    return (
      <ul style={{ paddingLeft: '1.2rem', lineHeight: '1.7' }}>
        {itemsArray.map((item, idx) => <li key={idx} style={{ marginBottom: '0.4rem' }}>{item}</li>)}
      </ul>
    );
  };

  const activeDosage = customDosage || result?.dosage_recommendation;

  return (
    <div style={{ maxWidth: '1360px', margin: '0 auto', padding: '1.5rem' }}>

      {/* Top Header */}
      <div className="agri-header-card">
        <h1 className="agri-app-title">
          🌱 HORTICBOTAI: Precision Crop Intelligence & Diagnostic Platform
        </h1>
        <p className="agri-app-subtitle">
          Next-Gen Cyber-Physical Agriculture Suite. Instant multi-spectral pigment analysis, CNN pest & disease isolation, semantic lesion segmentation, dynamic precision spray calculators, microclimate epidemiology radar, and multilingual farmer advisory.
        </p>
        <div className="badge-bar">
          <div className="agri-badge"><ShieldCheck size={16} /> Foliage Guard: <b>Active</b></div>
          <div className="agri-badge"><Sparkles size={16} /> Deep Learning: <b>Dual Neural Classifiers</b></div>
          <div className="agri-badge"><FlaskConical size={16} /> Spectral Indices: <b>ExG & CRI Proxies</b></div>
          <div className="agri-badge"><Target size={16} /> Severity Engine: <b>HSV/LAB Segmentation</b></div>
          <div className="agri-badge"><CloudSun size={16} /> Weather Radar: <b>Epidemiology AI</b></div>
          <a className="agri-badge" href="#farm" style={{ textDecoration: 'none' }}><Sparkles size={16} /> <b>My farm: spray, prices, fertilizer, profit</b></a>
          <a className="agri-badge" href="#admin" style={{ textDecoration: 'none' }}><ShieldCheck size={16} /> <b>Administrator</b></a>
        </div>
      </div>

      {/* Control Panel: API Key & Spectral Variant Settings */}
      <div className="card-section">
        <div className="section-title">
          <Sliders size={20} color="#059669" /> System Control & Voice AI Settings
        </div>
        <div className="grid-2">
          <div>
            <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.4rem', color: '#475569' }}>
              🔑 Advisory API Key (Groq / OpenAI / NVIDIA NIM)
            </label>
            <input
              type="password"
              placeholder="Enter API key for live LLM Advisory (Optional)..."
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <span style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem', display: 'block' }}>
              {apiKey ? "✨ Live Cloud LLM Advisory Active" : "⚡ Offline Local LLM (agri-qwen:7b) Active"}
            </span>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.4rem', color: '#475569' }}>
              🧪 Carotenoid (CRI) Proxy Variant
            </label>
            <select value={criVariant} onChange={(e) => setCriVariant(e.target.value)}>
              <option value="CRI1">CRI1: (1/Blue) - (1/Green) [Standard Proxy]</option>
              <option value="CRI2">CRI2: (1/Blue) - (1/Red) [Enhanced Red Edge Proxy]</option>
            </select>
            <span style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem', display: 'block' }}>
              Select Carotenoid Reflectance Index proxy algorithm variant.
            </span>
          </div>
        </div>

        <div className="grid-2" style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.4rem', color: '#475569' }}>
              🎙️ ElevenLabs Voice Key (Optional)
            </label>
            <input
              type="password"
              placeholder="Enter ElevenLabs API key for Studio Voice (Optional)..."
              value={elevenLabsKey}
              onChange={(e) => setElevenLabsKey(e.target.value)}
            />
            <span style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem', display: 'block' }}>
              {elevenLabsKey ? "✨ ElevenLabs Multilingual v2 Voice Active" : "⚡ High-Fidelity Indic Neural Audio Stream Active (Zero-Cost)"}
            </span>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.4rem', color: '#475569' }}>
              🗣️ AI Agronomist Voice Persona
            </label>
            <select value={elevenLabsVoice} onChange={(e) => setElevenLabsVoice(e.target.value)}>
              <option value="21m00Tcm4TlvDq8ikWAM">Rachel — Warm & Empathetic Advisor (Default)</option>
              <option value="pNInz6obpgDQGcFmaJgB">Adam — Clear & Authoritative Agronomist</option>
              <option value="ErXwobaYiN019PkySvjV">Antoni — Calm & Grounded Elder Advisor</option>
            </select>
            <span style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '0.2rem', display: 'block' }}>
              Select neural voice persona for Tamil, Hindi, and Indian language speech.
            </span>
          </div>
        </div>
      </div>

      {/* Step 1 & Step 2 Layout */}
      <div className="grid-2" style={{ marginBottom: '1.8rem' }}>

        {/* Step 1: Crop Selection */}
        <div className="card-section" style={{ marginBottom: 0 }}>
          <div className="section-title">
            <Leaf size={20} color="#059669" /> Step 1: Select Target Crop
          </div>
          <select
            value={selectedCrop}
            onChange={(e) => setSelectedCrop(e.target.value)}
            style={{ fontSize: '1.1rem', fontWeight: '600' }}
          >
            {(crops.length > 0 ? crops : Object.keys(CROP_ICONS)).map((c) => (
              <option key={c} value={c}>
                {CROP_ICONS[c] || '🌱'} {c}
              </option>
            ))}
          </select>
          <div style={{ marginTop: '1.2rem', background: '#f0fdf4', padding: '1rem', borderRadius: '12px', border: '1px solid #bbf7d0' }}>
            <p style={{ fontSize: '0.88rem', color: '#166534' }}>
              Selected Crop: <b>{CROP_ICONS[selectedCrop] || '🌱'} {selectedCrop}</b>
            </p>
            <p style={{ fontSize: '0.8rem', color: '#15803d', marginTop: '0.3rem' }}>
              Target neural network weights & customized agronomic diagnostic thresholds are loaded for {selectedCrop}.
            </p>
          </div>
        </div>

        {/* Step 2: Image Acquisition */}
        <div className="card-section" style={{ marginBottom: 0 }}>
          <div className="section-title">
            <Camera size={20} color="#059669" /> Step 2: Acquire Leaf Photo
          </div>

          {!cameraActive ? (
            <div>
              <div
                className="dropzone"
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
              >
                <Upload size={36} color="#059669" style={{ margin: '0 auto 0.5rem auto' }} />
                <p style={{ fontWeight: '700', color: '#0f172a' }}>Click or Drag & Drop Leaf Image</p>
                <p style={{ fontSize: '0.82rem', color: '#64748b' }}>Supports JPG, PNG, WEBP, BMP, TIFF</p>
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={(e) => e.target.files && handleFileChange(e.target.files[0])}
                  accept="image/*"
                  style={{ display: 'none' }}
                />
              </div>
              <button
                onClick={startCamera}
                style={{ marginTop: '0.75rem', width: '100%', background: '#e2e8f0', color: '#1e293b', border: 'none', padding: '0.6rem', borderRadius: '10px', fontWeight: '600', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}
              >
                <Camera size={16} /> Use Live Web Camera
              </button>
            </div>
          ) : (
            <div style={{ textAlign: 'center' }}>
              <video ref={videoRef} autoPlay playsInline style={{ width: '100%', borderRadius: '12px', height: '200px', objectFit: 'cover' }} />
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button onClick={capturePhoto} className="btn-primary" style={{ flex: 1, padding: '0.6rem' }}>📸 Snap Photo</button>
                <button onClick={stopCamera} style={{ padding: '0.6rem 1rem', background: '#cbd5e1', border: 'none', borderRadius: '10px', fontWeight: '600', cursor: 'pointer' }}>Cancel</button>
              </div>
            </div>
          )}
        </div>

      </div>

      {/* Image Preview & Run Button */}
      {imagePreview && (
        <div className="card-section" style={{ textAlign: 'center' }}>
          <img
            src={imagePreview}
            alt="Leaf preview"
            style={{ maxHeight: '280px', borderRadius: '16px', border: '2px solid #e2e8f0', boxShadow: '0 4px 12px rgba(0,0,0,0.06)' }}
          />
          <div style={{ marginTop: '1.2rem', maxWidth: '420px', margin: '1.2rem auto 0 auto' }}>
            <button
              onClick={runDiagnosis}
              disabled={loading}
              className="btn-primary"
            >
              {loading ? <RefreshCw className="animate-spin" size={20} /> : <Sparkles size={20} />}
              {loading ? 'Executing AI & Spectral Analytics...' : '🚀 RUN FULL DIAGNOSIS'}
            </button>
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div style={{ background: '#fee2e2', border: '1px solid #fca5a5', color: '#991b1b', padding: '1rem 1.5rem', borderRadius: '16px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
          <AlertTriangle size={24} />
          <div>
            <b>Diagnosis Error:</b> {error}
          </div>
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div>

          {/* Non-plant error check */}
          {!result.is_valid_plant ? (
            <div style={{ background: '#fef2f2', border: '2px solid #f87171', color: '#991b1b', padding: '1.5rem', borderRadius: '20px', marginBottom: '2rem', textAlign: 'center' }}>
              <AlertTriangle size={36} style={{ margin: '0 auto 0.5rem auto' }} />
              <h2 style={{ fontFamily: 'var(--font-heading)', fontWeight: '800' }}>Invalid Image Detected</h2>
              <p>{result.validation_error || 'The image uploaded does not appear to be a valid plant leaf.'}</p>
              <p style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: '#7f1d1d' }}>Please upload a clear, close-up photograph of a plant leaf.</p>
            </div>
          ) : (
            <div>
              {/* Plant Species Auto-Classifier Badge */}
              {result.crop_classification?.ok && (
                <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '1.1rem 1.4rem', borderRadius: '18px', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.8rem', boxShadow: '0 4px 15px rgba(4,120,87,0.06)' }}>
                  <div>
                    <span style={{ fontSize: '0.82rem', color: '#047857', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      🔍 Plant Species Neural Classifier Result
                    </span>
                    <h3 style={{ fontSize: '1.4rem', fontWeight: '800', color: '#064e3b', margin: '0.2rem 0' }}>
                      {CROP_ICONS[result.crop] || '🌱'} Identified Crop: <b>{result.crop}</b>
                    </h3>
                    <span style={{ fontSize: '0.88rem', color: '#047857' }}>
                      Species Identification Confidence: <b>{result.crop_classification.confidence}%</b>
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', background: 'white', padding: '0.6rem 1.1rem', borderRadius: '14px', border: '1px solid #6ee7b7', color: '#064e3b', fontWeight: '600' }}>
                    ✅ Diagnostic models auto-calibrated for {result.crop}
                  </div>
                </div>
              )}

              {/* Overall Health Score Card */}
              <div className="health-score-card">
                <div style={{ fontFamily: 'var(--font-heading)', fontSize: '1rem', fontWeight: '800', color: '#166534', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  Overall Plant Health Index ({CROP_ICONS[result.crop] || '🌱'} {result.crop})
                </div>
                <div className="health-score-num">
                  {result.overall?.overall_score != null ? Math.round(result.overall.overall_score) : 'N/A'}
                  <span style={{ fontSize: '2rem', opacity: 0.6 }}>/100</span>
                </div>
                <div className="health-badge">
                  {result.overall?.overall_status || 'UNAVAILABLE'}
                </div>
                <div style={{ color: '#4b5563', fontSize: '0.92rem', marginTop: '0.6rem' }}>
                  Diagnostic Confidence: <b>{result.overall?.assessment_confidence || 'N/A'}</b>
                </div>
              </div>

              {/* 6 Core Diagnostic Modules Breakdown */}
              <h2 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.4rem', fontWeight: '800', marginBottom: '1rem', color: '#0f172a' }}>
                📊 Multi-Spectral & AI Diagnostic Modules
              </h2>

              <div className="grid-6" style={{ marginBottom: '2rem' }}>

                {/* 1. Pest Card */}
                <div className={`diag-card ${result.pest?.is_healthy_class || result.pest?.identified === 'No Pest' || !result.pest?.pest_detected ? 'healthy' : 'alert'}`}>
                  <div>
                    <div className="diag-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>🐛 Insect Pest</span>
                      {result.pest?.pest_detected ? (
                        <span className="pill-bad">INFESTATION</span>
                      ) : (result.pest?.display_name?.includes('Verification') || result.pest?.rejection_reason?.includes('Verification')) ? (
                        <span className="pill-warn">VERIFICATION REQ.</span>
                      ) : (
                        <span className="pill-ok">CLEAN FOLIAGE</span>
                      )}
                    </div>
                    <div className="metric-row"><span className="metric-label">Identified:</span> <span className="metric-val">{result.pest?.display_name || 'No Visible Pest'}</span></div>
                    <div className="metric-row">
                      <span className="metric-label">Model Top-1:</span>
                      <span className="metric-val" style={{ fontSize: '0.85rem' }}>
                        {result.pest?.top_prediction || result.pest?.raw_class || 'N/A'} ({result.pest?.confidence ? `${result.pest.confidence.toFixed(1)}%` : 'N/A'})
                      </span>
                    </div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Math.min(Math.max(result.pest?.confidence || 0, 5), 100)}%`, backgroundColor: !result.pest?.pest_detected ? '#10b981' : '#ef4444' }} />
                    </div>

                    {/* Diagnostics & Explainability Telemetry */}
                    {result.pest?.probability_margin != null && (
                      <div className="metric-row" style={{ fontSize: '0.82rem' }}>
                        <span className="metric-label">Prob Margin (Δp):</span>
                        <span className="metric-val" style={{ color: result.pest.probability_margin >= 25 ? '#047857' : '#d97706', fontWeight: '600' }}>
                          {result.pest.probability_margin}% {result.pest.probability_margin < 25 ? '(High Entropy)' : '(Distinct)'}
                        </span>
                      </div>
                    )}
                    {result.pest?.evidence_score != null && (
                      <div className="metric-row" style={{ fontSize: '0.82rem' }}>
                        <span className="metric-label">Visual Evidence:</span>
                        <span className="metric-val" style={{ color: result.pest.evidence_score >= 0.35 ? '#b91c1c' : '#047857', fontWeight: '600' }}>
                          {(result.pest.evidence_score * 100).toFixed(0)}% {result.pest.evidence_score < 0.35 ? '(No Insect Bodies)' : '(Anomaly Found)'}
                        </span>
                      </div>
                    )}

                    <div className="metric-row" style={{ marginTop: '0.3rem' }}>
                      <span className="metric-label">Health Score:</span>
                      <span className="metric-val">{result.pest?.score != null ? Math.round(result.pest.score) : 100}/100</span>
                    </div>
                  </div>

                  {result.pest?.rejection_reason && (
                    <div style={{ fontSize: '0.78rem', background: '#f8fafc', padding: '0.45rem 0.65rem', borderRadius: '8px', border: '1px solid #e2e8f0', color: '#64748b', marginTop: '0.5rem', lineHeight: '1.3' }}>
                      ℹ️ <b>Open-Set Gate:</b> {result.pest.rejection_reason}
                    </div>
                  )}

                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Status:</span>
                    <span className={getStatusBadgeClass(result.pest?.status)} style={{ fontSize: '0.78rem', maxWidth: '65%', textAlign: 'right', whiteSpace: 'normal' }}>
                      {result.pest?.status || 'N/A'}
                    </span>
                  </div>
                </div>

                {/* 2. Disease Card */}
                <div className={`diag-card ${result.disease?.identified === 'Healthy' ? 'healthy' : 'alert'}`}>
                  <div>
                    <div className="diag-title">🍃 Foliar Disease</div>
                    <div className="metric-row"><span className="metric-label">Identified:</span> <span className="metric-val">{result.disease?.display_name || 'Healthy'}</span></div>
                    <div className="metric-row"><span className="metric-label">Confidence:</span> <span className="metric-val">{result.disease?.confidence ? `${result.disease.confidence.toFixed(1)}%` : 'N/A'}</span></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Math.min(Math.max(result.disease?.confidence || 0, 5), 100)}%`, backgroundColor: result.disease?.identified === 'Healthy' ? '#10b981' : '#ef4444' }} />
                    </div>
                    <div className="metric-row"><span className="metric-label">Score:</span> <span className="metric-val">{result.disease?.score != null ? Math.round(result.disease.score) : 100}/100</span></div>
                  </div>
                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Status:</span>
                    <span className={getStatusBadgeClass(result.disease?.status)}>{result.disease?.status || 'N/A'}</span>
                  </div>
                </div>

                {/* 3. Disease Severity & Lesion Segmentation Card (NEW FEATURE 1) */}
                <div className="diag-card severity">
                  <div>
                    <div className="diag-title">🎯 Lesion Severity</div>
                    <div className="metric-row"><span className="metric-label">Affected Area:</span> <span className="metric-val" style={{ color: '#b45309' }}>{result.severity?.affected_percentage != null ? `${result.severity.affected_percentage}%` : '0.0%'}</span></div>
                    <div className="metric-row"><span className="metric-label">Healthy Area:</span> <span className="metric-val">{result.severity?.healthy_percentage != null ? `${result.severity.healthy_percentage}%` : '100%'}</span></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Math.min(Math.max(result.severity?.affected_percentage || 0, 5), 100)}%`, backgroundColor: '#f59e0b' }} />
                    </div>
                    <div className="metric-row"><span className="metric-label">Stage:</span> <span className="metric-val" style={{ fontSize: '0.85rem' }}>{result.severity?.severity_stage || 'Healthy'}</span></div>
                  </div>
                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Health Score:</span>
                    <span className="pill-warn">{result.severity?.severity_score != null ? `${Math.round(result.severity.severity_score)}/100` : '95/100'}</span>
                  </div>
                </div>

                {/* 4. Plant Nutrient Deficiency Card (NEW FEATURE 2) */}
                <div className="diag-card nutrient">
                  <div>
                    <div className="diag-title">🧪 Nutrient Status</div>
                    <div className="metric-row"><span className="metric-label">Primary:</span> <span className="metric-val" style={{ color: '#7e22ce' }}>{result.nutrients?.primary_deficiency || 'Optimal (NPK)'}</span></div>
                    <div className="metric-row"><span className="metric-label">Deficiency:</span> <span className="metric-val">{result.nutrients?.has_deficiency ? 'Detected' : 'None'}</span></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${result.nutrients?.has_deficiency ? 65 : 10}%`, backgroundColor: '#c084fc' }} />
                    </div>
                    <div className="metric-row"><span className="metric-label">Affected Zone:</span> <span className="metric-val" style={{ fontSize: '0.82rem' }}>{result.nutrients?.affected_leaf_zone || 'Uniform'}</span></div>
                  </div>
                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Severity:</span>
                    <span className="pill-purple">{result.nutrients?.severity || 'Low'}</span>
                  </div>
                </div>

                {/* 5. NDRE Chlorophyll Card */}
                <div className={`diag-card ${(result.ndre?.score || 0) >= 70 ? 'healthy' : 'alert'}`}>
                  <div>
                    <div className="diag-title">🌿 ExG Chlorophyll</div>
                    <div className="metric-row"><span className="metric-label">Index Proxy:</span> <span className="metric-val">{result.ndre?.value != null ? result.ndre.value.toFixed(3) : 'N/A'}</span></div>
                    <div className="metric-row"><span className="metric-label">Spectral Score:</span> <span className="metric-val">{result.ndre?.score != null ? Math.round(result.ndre.score) : 0}/100</span></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Math.min(Math.max(result.ndre?.score || 0, 5), 100)}%`, backgroundColor: '#10b981' }} />
                    </div>
                    <div className="metric-row"><span className="metric-label">Threshold:</span> <span className="metric-val">{result.ndre?.status || 'N/A'}</span></div>
                  </div>
                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Status:</span>
                    <span className={getStatusBadgeClass(result.ndre?.status)}>{result.ndre?.status || 'N/A'}</span>
                  </div>
                </div>

                {/* 6. CRI Carotenoid Card */}
                <div className={`diag-card ${(result.cri?.score || 0) >= 70 ? 'healthy' : 'alert'}`}>
                  <div>
                    <div className="diag-title">🥕 Carotenoid Stress</div>
                    <div className="metric-row"><span className="metric-label">Index Proxy:</span> <span className="metric-val">{result.cri?.value != null ? result.cri.value.toFixed(3) : 'N/A'}</span></div>
                    <div className="metric-row"><span className="metric-label">Stress Score:</span> <span className="metric-val">{result.cri?.score != null ? Math.round(result.cri.score) : 0}/100</span></div>
                    <div className="progress-bar">
                      <div className="progress-fill" style={{ width: `${Math.min(Math.max(result.cri?.score || 0, 5), 100)}%`, backgroundColor: '#f97316' }} />
                    </div>
                    <div className="metric-row"><span className="metric-label">Variant:</span> <span className="metric-val">{result.cri?.variant || 'CRI1'}</span></div>
                  </div>
                  <div className="metric-row" style={{ marginTop: '0.8rem' }}>
                    <span className="metric-label">Status:</span>
                    <span className={getStatusBadgeClass(result.cri?.status)}>{result.cri?.status || 'N/A'}</span>
                  </div>
                </div>

              </div>

              {/* Spectral & Lesion Heatmaps Display Section (NEW FEATURE 1 OVERLAY MAP INCLUDED) */}
              <div className="card-section">
                <div className="section-title">
                  <Eye size={20} color="#059669" /> Multi-Spectral & Semantic Lesion Heatmaps
                </div>
                <div className="grid-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>

                  {/* Original Image */}
                  <div style={{ textAlign: 'center' }}>
                    <p style={{ fontWeight: '700', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#334155' }}>📸 Original Leaf Frame</p>
                    <img src={imagePreview} alt="Original Leaf" style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '14px', border: '1px solid #cbd5e1' }} />
                  </div>

                  {/* Grad-CAM explainability: where the CNN looked */}
                  {result.gradcam?.ok && (
                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontWeight: '700', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#7e22ce', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.35rem' }}>
                        <ScanEye size={16} /> AI Focus Map (Grad-CAM)
                      </p>
                      <img src={result.gradcam.heatmap_base64} alt="Grad-CAM heatmap" style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '14px', border: '1px solid #d8b4fe' }} />
                      <p style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '0.35rem' }}>
                        Red = regions the {result.gradcam.target} model relied on for <b>{result.gradcam.label}</b>. Outlined zones cover {result.gradcam.focus_area_pct}% of the leaf.
                      </p>
                    </div>
                  )}

                  {/* ExG Chlorophyll Heatmap */}
                  {result.ndre?.heatmap_base64 && (
                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontWeight: '700', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#166534' }}>🌿 ExG Chlorophyll Heatmap</p>
                      <img src={result.ndre.heatmap_base64} alt="NDRE Heatmap" style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '14px', border: '1px solid #86efac' }} />
                    </div>
                  )}

                  {/* CRI Carotenoid Heatmap */}
                  {result.cri?.heatmap_base64 && (
                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontWeight: '700', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#9a3412' }}>🥕 CRI Carotenoid Heatmap</p>
                      <img src={result.cri.heatmap_base64} alt="CRI Heatmap" style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '14px', border: '1px solid #fdba74' }} />
                    </div>
                  )}

                  {/* Lesion Segmentation Map Overlay */}
                  {result.severity?.visual_map_base64 && (
                    <div style={{ textAlign: 'center' }}>
                      <p style={{ fontWeight: '700', fontSize: '0.9rem', marginBottom: '0.4rem', color: '#dc2626' }}>🎯 Lesion & Necrosis Map</p>
                      <img src={result.severity.visual_map_base64} alt="Lesion Map" style={{ width: '100%', height: '220px', objectFit: 'cover', borderRadius: '14px', border: '1px solid #fca5a5' }} />
                    </div>
                  )}

                </div>
              </div>

              {/* NEW FEATURE 3: Interactive Precision Dosage & Spray Calculator */}
              <div className="card-section">
                <div className="section-title">
                  <Calculator size={20} color="#059669" /> Precision Dosage & Tank Sprayer Calculator
                </div>
                <p style={{ fontSize: '0.9rem', color: '#64748b', marginBottom: '1.2rem' }}>
                  Dynamically compute active chemical dilution, knapsack tank fills, product requirements, and organic alternatives based on your farm acreage.
                </p>

                {/* Interactive Sliders */}
                <div className="grid-3" style={{ background: '#f8fafc', padding: '1.2rem', borderRadius: '16px', border: '1px solid #e2e8f0', marginBottom: '1.4rem' }}>

                  {/* Target Selector */}
                  <div>
                    <label className="slider-name">Target Pest / Disease / Deficiency</label>
                    <select
                      value={dosageTarget}
                      onChange={(e) => {
                        setDosageTarget(e.target.value);
                        calculateDynamicDosage(e.target.value, fieldAcreage, tankCapacity, dosageMode);
                      }}
                      style={{ marginTop: '0.4rem' }}
                    >
                      <option value="Early Blight">Early Blight (Alternaria solani)</option>
                      <option value="Late Blight">Late Blight (Phytophthora infestans)</option>
                      <option value="Powdery Mildew">Powdery Mildew (Oidium spp.)</option>
                      <option value="Downy Mildew">Downy Mildew (Pseudoperonospora)</option>
                      <option value="Bacterial Spot">Bacterial Spot (Xanthomonas)</option>
                      <option value="Septoria Leaf Spot">Septoria Leaf Spot</option>
                      <option value="Aphids">Aphids (Aphis gossypii)</option>
                      <option value="Mites">Spider Mites (Tetranychidae)</option>
                      <option value="Armyworm">Fall Armyworm (Spodoptera)</option>
                      <option value="Bollworm">Helicoverpa Bollworm</option>
                      <option value="Nitrogen Deficiency">Nitrogen (N) Deficiency</option>
                      <option value="Phosphorus Deficiency">Phosphorus (P) Deficiency</option>
                      <option value="Potassium Deficiency">Potassium (K) Deficiency</option>
                      <option value="Iron Deficiency">Iron (Fe) Deficiency</option>
                      <option value="Zinc Deficiency">Zinc (Zn) Deficiency</option>
                    </select>
                  </div>

                  {/* Acreage Slider */}
                  <div className="slider-group">
                    <div className="slider-label-row">
                      <span className="slider-name">🌾 Field Size (Acres)</span>
                      <span className="slider-value-badge">{fieldAcreage.toFixed(1)} Acres</span>
                    </div>
                    <input
                      type="range"
                      min="0.1"
                      max="20.0"
                      step="0.1"
                      value={fieldAcreage}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setFieldAcreage(val);
                        calculateDynamicDosage(dosageTarget, val, tankCapacity, dosageMode);
                      }}
                    />
                  </div>

                  {/* Tank Capacity Slider */}
                  <div className="slider-group">
                    <div className="slider-label-row">
                      <span className="slider-name">🛢️ Sprayer Tank Capacity</span>
                      <span className="slider-value-badge">{tankCapacity} Liters</span>
                    </div>
                    <input
                      type="range"
                      min="5"
                      max="50"
                      step="1"
                      value={tankCapacity}
                      onChange={(e) => {
                        const val = parseFloat(e.target.value);
                        setTankCapacity(val);
                        calculateDynamicDosage(dosageTarget, fieldAcreage, val, dosageMode);
                      }}
                    />
                  </div>

                </div>

                {/* Dosage Results Render */}
                {activeDosage && (
                  <div className="grid-2">

                    {/* Chemical Protocol */}
                    {activeDosage.chemical_treatment && (
                      <div className="dosage-card chemical">
                        <div className="dosage-header">
                          <span style={{ color: '#c2410c' }}>🧪 Chemical Spray Prescription</span>
                          <span className="pill-warn">{activeDosage.chemical_treatment.product_name}</span>
                        </div>

                        <div className="dosage-metric-grid">
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Dose / Liter</div>
                            <div className="dosage-stat-num">{activeDosage.chemical_treatment.dilution_rate_per_liter}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Per {tankCapacity}L Tank</div>
                            <div className="dosage-stat-num">{activeDosage.chemical_treatment.chemical_per_tank}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Total Product</div>
                            <div className="dosage-stat-num">{activeDosage.chemical_treatment.total_chemical_needed}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Total Water</div>
                            <div className="dosage-stat-num">{activeDosage.chemical_treatment.total_water_liters} L</div>
                          </div>
                        </div>

                        <div style={{ fontSize: '0.88rem', color: '#7c2d12', marginTop: '0.6rem' }}>
                          <p><b>⏱️ Tank Passes Needed:</b> {activeDosage.chemical_treatment.sprayer_tanks_needed} full tank(s)</p>
                          <p><b>⚠️ Pre-Harvest Interval (PHI):</b> {activeDosage.chemical_treatment.pre_harvest_interval_days} Days</p>
                          <p><b>🛡️ Safety:</b> {activeDosage.chemical_treatment.safety_precautions}</p>
                        </div>
                      </div>
                    )}

                    {/* Organic Protocol */}
                    {activeDosage.organic_treatment && (
                      <div className="dosage-card organic">
                        <div className="dosage-header">
                          <span style={{ color: '#15803d' }}>🌿 Organic / Bio-Fungicide Solution</span>
                          <span className="pill-ok">{activeDosage.organic_treatment.product_name}</span>
                        </div>

                        <div className="dosage-metric-grid">
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Dose / Liter</div>
                            <div className="dosage-stat-num">{activeDosage.organic_treatment.dilution_rate_per_liter}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Per {tankCapacity}L Tank</div>
                            <div className="dosage-stat-num">{activeDosage.organic_treatment.amount_per_tank}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Total Organic</div>
                            <div className="dosage-stat-num">{activeDosage.organic_treatment.total_amount_needed}</div>
                          </div>
                          <div className="dosage-stat-box">
                            <div className="dosage-stat-title">Total Water</div>
                            <div className="dosage-stat-num">{activeDosage.organic_treatment.total_water_liters} L</div>
                          </div>
                        </div>

                        <div style={{ fontSize: '0.88rem', color: '#166534', marginTop: '0.6rem' }}>
                          <p><b>🍃 Preparation:</b> {activeDosage.organic_treatment.preparation_method}</p>
                          <p><b>⏰ Frequency:</b> {activeDosage.organic_treatment.application_frequency}</p>
                          <p><b>✅ Bio Safety:</b> Zero chemical residue, safe for pollinators and organic certification.</p>
                        </div>
                      </div>
                    )}

                  </div>
                )}
              </div>

              {/* NEW FEATURE 4: Microclimate Weather & Disease Outbreak Risk Radar */}
              <div className="card-section">
                <div className="section-title">
                  <CloudSun size={20} color="#059669" /> Microclimate Weather & Disease Outbreak Risk Radar
                </div>

                <div className="weather-container">

                  {/* Location Bar */}
                  <div style={{ display: 'flex', gap: '0.8rem', marginBottom: '1.2rem', flexWrap: 'wrap', alignItems: 'center' }}>
                    <div style={{ flex: 1, minWidth: '240px', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'white', padding: '0.4rem 0.8rem', borderRadius: '12px', border: '1px solid #cbd5e1' }}>
                      <MapPin size={18} color="#0284c7" />
                      <input
                        type="text"
                        value={weatherLocation}
                        onChange={(e) => setWeatherLocation(e.target.value)}
                        placeholder="Enter City / Farm Location..."
                        style={{ border: 'none', padding: '0.3rem', outline: 'none' }}
                      />
                    </div>
                    <button
                      onClick={() => fetchWeatherRisk(weatherLocation, result.crop, result.disease?.identified)}
                      className="btn-secondary"
                      disabled={loadingWeather}
                    >
                      {loadingWeather ? <RefreshCw className="animate-spin" size={16} /> : <RefreshCw size={16} />}
                      Update Radar
                    </button>
                  </div>

                  {weatherData && !weatherData.weather && (
                    <div style={{ background: '#f1f5f9', border: '1px solid #cbd5e1', padding: '1rem 1.4rem', borderRadius: '16px', color: '#334155' }}>
                      <b>Weather unavailable.</b> {weatherData.error || 'The weather service could not be reached.'}
                    </div>
                  )}

                  {weatherData && weatherData.weather && (
                    <div>
                      {/* Current Weather Bar */}
                      <div className="weather-metric-bar">
                        <div className="weather-metric-item">
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '700' }}>TEMPERATURE</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0f172a' }}>{weatherData.weather.current?.temp_c}°C</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{weatherData.weather.current?.temp_f}°F</div>
                        </div>
                        <div className="weather-metric-item">
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '700' }}>HUMIDITY</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0284c7' }}>{weatherData.weather.current?.humidity}%</div>
                          <div style={{ fontSize: '0.75rem', color: '#0284c7' }}>Spore Risk Window</div>
                        </div>
                        <div className="weather-metric-item">
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '700' }}>PRECIPITATION</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#2563eb' }}>{weatherData.weather.current?.precipitation_mm} mm</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Leaf Wetness</div>
                        </div>
                        <div className="weather-metric-item">
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '700' }}>WIND SPEED</div>
                          <div style={{ fontSize: '1.4rem', fontWeight: '800', color: '#0f172a' }}>{weatherData.weather.current?.wind_kph} km/h</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>Spray Drift Check</div>
                        </div>
                        <div className="weather-metric-item">
                          <div style={{ fontSize: '0.75rem', color: '#64748b', fontWeight: '700' }}>MICROCLIMATE</div>
                          <div style={{ fontSize: '0.95rem', fontWeight: '800', color: '#047857', marginTop: '0.2rem' }}>{weatherData.weather.current?.condition}</div>
                          <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{weatherData.weather.location}</div>
                        </div>
                      </div>

                      {/* Outbreak Alert Banner */}
                      {weatherData.risk_analysis && (
                        <div style={{ background: weatherData.risk_analysis.risk_color === 'red' ? '#fee2e2' : weatherData.risk_analysis.risk_color === 'orange' ? '#ffedd5' : '#fef9c3', border: '1px solid rgba(0,0,0,0.1)', padding: '1rem 1.4rem', borderRadius: '16px', marginBottom: '1.2rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                              <AlertTriangle size={22} color={weatherData.risk_analysis.risk_color === 'red' ? '#dc2626' : '#d97706'} />
                              <span style={{ fontWeight: '800', fontSize: '1.05rem', color: '#0f172a' }}>
                                Highest Outbreak Risk: <u>{weatherData.risk_analysis.highest_risk_disease}</u> ({weatherData.risk_analysis.risk_value}%)
                              </span>
                            </div>
                            <span className={weatherData.risk_analysis.risk_value >= 70 ? 'pill-bad' : 'pill-warn'}>
                              {weatherData.risk_analysis.risk_level} OUTBREAK RISK
                            </span>
                          </div>
                          <p style={{ fontSize: '0.9rem', color: '#334155', marginTop: '0.4rem', fontWeight: '500' }}>
                            <b>Recommended Action:</b> {weatherData.risk_analysis.recommended_action}
                          </p>
                          {weatherData.risk_analysis.warning && (
                            <p style={{ fontSize: '0.85rem', color: '#b91c1c', marginTop: '0.3rem', fontWeight: '600' }}>
                              {weatherData.risk_analysis.warning}
                            </p>
                          )}
                        </div>
                      )}

                      {/* 6 Disease Risk Gauges Grid */}
                      {weatherData.risk_analysis?.disease_risks && (
                        <div className="weather-risk-grid">
                          {Object.entries(weatherData.risk_analysis.disease_risks).map(([dName, dRisk]) => (
                            <div key={dName} className="risk-item">
                              <div className="risk-item-header">
                                <span style={{ color: '#1e293b' }}>{dName}</span>
                                <span style={{ color: dRisk >= 70 ? '#dc2626' : dRisk >= 40 ? '#d97706' : '#166534', fontWeight: '800' }}>{dRisk}%</span>
                              </div>
                              <div className="risk-track">
                                <div
                                  className="risk-bar-fill"
                                  style={{
                                    width: `${dRisk}%`,
                                    backgroundColor: dRisk >= 70 ? '#ef4444' : dRisk >= 40 ? '#f59e0b' : '#10b981'
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                    </div>
                  )}

                </div>
              </div>

              {/* AI Farmer Advisory Console (5 Tabs) */}
              <div className="card-section">
                <div className="section-title">
                  <Sparkles size={20} color="#059669" /> Agronomic Advisory Console
                </div>

                <div className="tabs-container">
                  <button className={`tab-btn ${activeTab === 'emergency' ? 'active' : ''}`} onClick={() => setActiveTab('emergency')}>
                    🚨 Emergency Actions
                  </button>
                  <button className={`tab-btn ${activeTab === 'timeline' ? 'active' : ''}`} onClick={() => setActiveTab('timeline')}>
                    🗓️ 24h-7d Schedule
                  </button>
                  <button className={`tab-btn ${activeTab === 'control' ? 'active' : ''}`} onClick={() => setActiveTab('control')}>
                    🛡️ Pest & Disease Control
                  </button>
                  <button className={`tab-btn ${activeTab === 'nutrition' ? 'active' : ''}`} onClick={() => setActiveTab('nutrition')}>
                    💧 Water & Soil Nutrition
                  </button>
                  <button className={`tab-btn ${activeTab === 'notes' ? 'active' : ''}`} onClick={() => setActiveTab('notes')}>
                    🔍 Risk & Field Notes
                  </button>
                </div>

                <div style={{ padding: '0.5rem 0' }}>
                  {activeTab === 'emergency' && (
                    <div>
                      {result.advice?.summary && (
                        <div style={{ background: '#f8fafc', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', borderLeft: '4px solid #059669' }}>
                          <h4 style={{ margin: '0 0 0.5rem 0', color: '#0f172a' }}>{result.advice.summary.headline}</h4>
                          <p style={{ margin: '0 0 0.25rem 0', color: '#334155' }}><strong>Severity:</strong> {result.advice.summary.severity} | <strong>Confidence:</strong> {result.advice.summary.confidence}</p>
                          <p style={{ margin: 0, color: '#475569', fontStyle: 'italic' }}>{result.advice.summary.farmer_message}</p>
                        </div>
                      )}
                      <div className="grid-2">
                      <div>
                      <h4 style={{ color: '#dc2626', marginBottom: '0.5rem', fontWeight: '700' }}>Emergency Actions</h4>
                      {(!result.advice?.emergency_actions || result.advice.emergency_actions.length === 0) ? (
                        <p style={{ color: '#94a3b8', fontStyle: 'italic' }}>No immediate emergency actions required.</p>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                          {result.advice.emergency_actions.map((act, i) => (
                            <div key={i} style={{ padding: '0.75rem', borderRadius: '8px', background: act.priority === 'HIGH' ? '#fee2e2' : '#f1f5f9', borderLeft: act.priority === 'HIGH' ? '4px solid #dc2626' : '4px solid #64748b' }}>
                              <strong style={{ color: act.priority === 'HIGH' ? '#b91c1c' : '#334155' }}>
                                [{act.priority}] {act.action}
                              </strong>
                              {act.reason && <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem', color: '#475569' }}>Because: {act.reason}</p>}
                            </div>
                          ))}
                        </div>
                      )}
                      </div>
                      <div>
                      {result.advice?.safety?.warnings && result.advice.safety.warnings.length > 0 && (
                        <div>
                           <h4 style={{ color: '#b91c1c', marginBottom: '0.5rem', fontWeight: '700' }}>Safety Warnings</h4>
                           {renderAdviceList(result.advice.safety.warnings)}
                        </div>
                      )}
                      </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'timeline' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#d97706', marginBottom: '0.5rem', fontWeight: '700' }}>Next 24 Hours</h4>
                        {renderAdviceList(result.advice?.schedule?.next_24_hours)}
                      </div>
                      <div>
                        <h4 style={{ color: '#2563eb', marginBottom: '0.5rem', fontWeight: '700' }}>Days 2-7</h4>
                        <div style={{ marginBottom: '1rem' }}>
                          <h5 style={{ margin: '0 0 0.25rem 0', color: '#1d4ed8' }}>Days 2-3</h5>
                          {renderAdviceList(result.advice?.schedule?.days_2_3)}
                        </div>
                        <div>
                          <h5 style={{ margin: '0 0 0.25rem 0', color: '#1d4ed8' }}>Days 4-7</h5>
                          {renderAdviceList(result.advice?.schedule?.days_4_7)}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'control' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#059669', marginBottom: '0.5rem', fontWeight: '700' }}>Findings & Verification</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Confirmed</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.confirmed_findings)}
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Possible</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.possible_findings)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Verification Steps</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.verification_steps)}
                        </div>
                      </div>
                      <div>
                        <h4 style={{ color: '#059669', marginBottom: '0.5rem', fontWeight: '700' }}>Control Methods</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Cultural</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.cultural_control)}
                        </div>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Biological</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.biological_control)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Chemical</h5>
                            {renderAdviceList(result.advice?.pest_disease_control?.chemical_control)}
                        </div>
                      </div>
                    </div>
                  )}

                  {activeTab === 'nutrition' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#0284c7', marginBottom: '0.5rem', fontWeight: '700' }}>Irrigation & Soil</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Irrigation Guidance</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.irrigation)}
                        </div>
                        <div>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Soil Actions</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.soil_actions)}
                        </div>
                      </div>
                      <div>
                        <h4 style={{ color: '#7c3aed', marginBottom: '0.5rem', fontWeight: '700' }}>Nutrient & Sensor Data</h4>
                        <div style={{ marginBottom: '1rem' }}>
                            <h5 style={{ margin: '0 0 0.25rem 0' }}>Nutrient Management</h5>
                            {renderAdviceList(result.advice?.water_soil_nutrition?.nutrient_actions)}
                        </div>
                        {result.advice?.water_soil_nutrition?.sensor_status && (
                            <div style={{ background: '#f3f4f6', padding: '0.75rem', borderRadius: '8px' }}>
                                <strong>Sensor Status:</strong> {result.advice.water_soil_nutrition.sensor_status}
                            </div>
                        )}
                      </div>
                    </div>
                  )}

                  {activeTab === 'notes' && (
                    <div className="grid-2">
                      <div>
                        <h4 style={{ color: '#475569', marginBottom: '0.5rem', fontWeight: '700' }}>Risk Assessment</h4>
                        <ul className="risk-list" style={{ paddingLeft: '1.2rem', lineHeight: '1.7', color: '#334155' }}>
                            {result.advice?.risk_field_notes?.disease_risk && <li><strong>Disease Risk:</strong> {result.advice.risk_field_notes.disease_risk}</li>}
                            {result.advice?.risk_field_notes?.pest_risk && <li><strong>Pest Risk:</strong> {result.advice.risk_field_notes.pest_risk}</li>}
                            {result.advice?.risk_field_notes?.spread_risk && <li><strong>Spread Risk:</strong> {result.advice.risk_field_notes.spread_risk}</li>}
                            {result.advice?.risk_field_notes?.environmental_risk && <li><strong>Environmental Risk:</strong> {result.advice.risk_field_notes.environmental_risk}</li>}
                        </ul>
                      </div>
                      <div>
                        <h4 style={{ color: '#475569', marginBottom: '0.5rem', fontWeight: '700' }}>Field Monitoring</h4>
                        {renderAdviceList(result.advice?.risk_field_notes?.monitoring_notes)}
                        {result.advice?.risk_field_notes?.next_scan && (
                            <div style={{ marginTop: '1rem', background: '#f8fafc', padding: '0.75rem', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <strong>Next Scan Recommended:</strong> {result.advice.risk_field_notes.next_scan}
                            </div>
                        )}
                         {result.advice?.safety?.chemical_disclaimer && (
                            <div style={{ marginTop: '1rem', background: '#fffbeb', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', color: '#b45309' }}>
                                <strong>Disclaimer:</strong> {result.advice.safety.chemical_disclaimer}
                            </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Note: UI dynamically injected via patch */}

                </div>
              </div>

              {/* NEW FEATURE 5: Multilingual AI Agronomist Chatbot */}
              <div className="card-section">
                <div className="section-title" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                    <MessageSquare size={20} color="#059669" /> Multilingual AI Agronomist Assistant
                  </div>

                  {/* Language Selector */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <Globe size={16} color="#64748b" />
                    <select
                      value={selectedLang}
                      onChange={(e) => handleLanguageChange(e.target.value)}
                      style={{ padding: '0.35rem 0.7rem', fontSize: '0.88rem', borderRadius: '8px', width: 'auto' }}
                    >
                      {languages.map(l => (
                        <option key={l.code} value={l.code}>
                          {l.flag} {l.name} ({l.native})
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {/* Chat Window */}
                <div className="chat-window">
                  <div className="chat-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <Bot size={20} />
                      <span style={{ fontWeight: '700' }}>HORTICBOTAI Virtual Agronomist</span>
                    </div>
                    <span style={{ fontSize: '0.8rem', opacity: 0.85 }}>Online | Regional AI Engine</span>
                  </div>

                  <div className="chat-body">
                    {chatMessages.map((msg, i) => (
                      <div key={i} className={`chat-bubble ${msg.sender}`}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.4rem', marginBottom: '0.2rem', fontSize: '0.75rem', opacity: 0.85 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            {msg.sender === 'bot' ? <Bot size={14} /> : <User size={14} />}
                            <span style={{ fontWeight: '600' }}>{msg.sender === 'bot' ? 'AI Assistant' : 'You'}</span>
                            <span>•</span>
                            <span>{msg.time}</span>
                          </div>
                          {msg.sender === 'bot' && (
                            <button
                              className={`voice-btn ${speakingIndex === i ? 'speaking' : ''} ${loadingAudioIndex === i ? 'loading' : ''}`}
                              onClick={() => speakText(msg.text, i)}
                              title={speakingIndex === i ? "Stop speaking" : loadingAudioIndex === i ? "Synthesizing voice audio..." : "Listen via Neural TTS (குரல் வாசிப்பு)"}
                              type="button"
                              disabled={loadingAudioIndex === i}
                            >
                              {loadingAudioIndex === i ? (
                                <>
                                  <RefreshCw className="animate-spin" size={12} />
                                  <span>Loading...</span>
                                </>
                              ) : speakingIndex === i ? (
                                <>
                                  <VolumeX size={13} />
                                  <span>Stop</span>
                                </>
                              ) : (
                                <>
                                  <Volume2 size={13} />
                                  <span>Voice</span>
                                </>
                              )}
                            </button>
                          )}
                        </div>
                        <div style={{ whiteSpace: 'pre-wrap' }}>{msg.text}</div>
                      </div>
                    ))}
                    {loadingChat && (
                      <div className="chat-bubble bot" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <RefreshCw className="animate-spin" size={16} />
                        <span>AI ஆலோசகர் சிந்தித்து பதிலளிக்கிறது...</span>
                      </div>
                    )}
                    <div ref={chatBottomRef} />
                  </div>

                  {/* Dynamic Quick Question Chips by Language */}
                  <div className="chat-chips">
                    {(QUICK_QUESTION_CHIPS[selectedLang] || QUICK_QUESTION_CHIPS['ta']).map((chip, idx) => (
                      <button key={idx} className="chat-chip" onClick={() => handleSendChat(chip.query)}>
                        {chip.label}
                      </button>
                    ))}
                  </div>

                  {/* Input Bar with NLP Voice Input */}
                  <div className="chat-input-bar">
                    <button
                      type="button"
                      className={`btn-mic ${isListening ? 'listening' : ''}`}
                      onClick={toggleListening}
                      title={isListening ? "Listening... Click to stop (பேசுவதை நிறுத்த கிளிக் செய்யவும்)" : "Speak via Microphone (மைக் மூலம் பேச கிளிக் செய்யவும்)"}
                    >
                      {isListening ? <MicOff size={18} /> : <Mic size={18} />}
                    </button>
                    <input
                      type="text"
                      placeholder={isListening ? "Listening to your voice (பேசுங்கள்... கேட்கிறது)..." : "பயிர் பாதுகாப்பு பற்றி கேளுங்கள் (Ask your agricultural question)..."}
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSendChat()}
                    />
                    <button
                      onClick={() => handleSendChat()}
                      disabled={loadingChat}
                      className="btn-primary"
                      style={{ width: 'auto', padding: '0.75rem 1.4rem' }}
                    >
                      <Send size={18} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Download Reports Button Row */}
              <div className="card-section">
                <div className="section-title">
                  <Download size={20} color="#059669" /> Export Diagnostic Reports
                </div>
                <div className="grid-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                  <button onClick={() => downloadReport('text')} className="btn-primary" style={{ background: '#334155' }}>
                    <FileText size={18} /> Download Text Report (.txt)
                  </button>
                  <button onClick={() => downloadReport('pdf')} className="btn-primary" style={{ background: '#dc2626' }}>
                    <FileText size={18} /> Download PDF Report (.pdf)
                  </button>
                  <button onClick={() => downloadReport('docx')} className="btn-primary" style={{ background: '#2563eb' }}>
                    <FileText size={18} /> Download Word Report (.docx)
                  </button>
                </div>
              </div>

            </div>
          )}

        </div>
      )}

      {/* Scan History & Health Trend */}
      {scanHistory.length > 0 && (
        <div className="card-section">
          <div className="section-title" style={{ justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <Clock size={20} color="#059669" /> Scan History & Health Trend
            </div>
            <button onClick={loadHistory} style={{ background: 'none', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '0.35rem 0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', color: '#475569', fontWeight: 600 }}>
              <RefreshCw size={14} /> Refresh
            </button>
          </div>

          {/* Oldest → newest so the bars read left-to-right as a recovery timeline */}
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '6px', height: '90px', padding: '0 0.25rem 0.5rem', borderBottom: '1px solid #e2e8f0', marginBottom: '1rem', overflowX: 'auto' }}>
            {[...scanHistory].reverse().map(scan => (
              <div
                key={scan.id}
                title={`${scan.timestamp?.replace('T', ' ')} • ${scan.crop} • ${scan.overall_score ?? '--'}/100`}
                style={{ flex: '0 0 22px', height: `${Math.max(scan.overall_score || 0, 4)}%`, background: scoreColor(scan.overall_score), borderRadius: '6px 6px 2px 2px', opacity: 0.85 }}
              />
            ))}
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
              <thead>
                <tr style={{ textAlign: 'left', color: '#64748b', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '0.5rem' }}>When</th>
                  <th style={{ padding: '0.5rem' }}>Crop</th>
                  <th style={{ padding: '0.5rem' }}>Disease</th>
                  <th style={{ padding: '0.5rem' }}>Pest</th>
                  <th style={{ padding: '0.5rem' }}>Affected</th>
                  <th style={{ padding: '0.5rem' }}>Health</th>
                  <th style={{ padding: '0.5rem' }}></th>
                </tr>
              </thead>
              <tbody>
                {scanHistory.map(scan => (
                  <tr key={scan.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '0.5rem', whiteSpace: 'nowrap' }}>{scan.timestamp?.replace('T', ' ').slice(0, 16)}</td>
                    <td style={{ padding: '0.5rem' }}>{CROP_ICONS[scan.crop] || '🌱'} {scan.crop}</td>
                    <td style={{ padding: '0.5rem' }}>{scan.disease_label || '—'}</td>
                    <td style={{ padding: '0.5rem' }}>{scan.pest_label || '—'}</td>
                    <td style={{ padding: '0.5rem' }}>{scan.severity_pct != null ? `${scan.severity_pct}%` : '—'}</td>
                    <td style={{ padding: '0.5rem', fontWeight: 800, color: scoreColor(scan.overall_score) }}>
                      {scan.overall_score != null ? Math.round(scan.overall_score) : '--'}/100
                    </td>
                    <td style={{ padding: '0.5rem', textAlign: 'right' }}>
                      <button onClick={() => deleteHistoryScan(scan.id)} title="Delete scan" style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8' }}>
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}

// Main App component with Error Boundary wrapper
export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onHash = () => setHash(window.location.hash);
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  return (
    <ErrorBoundary>
      {hash === '#admin' ? <AdminPanel apiBase={API_BASE} /> : hash === '#farm' ? <FarmerPanel apiBase={API_BASE} /> : <AppContent />}
    </ErrorBoundary>
  );
}
