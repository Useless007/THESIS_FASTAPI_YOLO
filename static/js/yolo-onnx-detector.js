// Real-time YOLOv10 object detection in browser using ONNX
class YOLODetector {
  constructor() {
    this.model = null;
    this.session = null;
    this.modelLoaded = false;
    this.canvas = null;
    this.ctx = null;
    this.video = null;
    this.isProcessing = false;
    this.confidenceThreshold = 0.3;
    this.classColors = {};
    this.labels = null;
    this.isRunning = false;
    this.loadingMessage = null;
    this.modelInputName = null; // For dynamically determining input name
  }

  async initialize(videoElement, canvasElement) {
    try {
      console.log("Initializing YOLOv10 ONNX detector");
      this.video = videoElement;
      this.canvas = canvasElement;
      this.ctx = this.canvas.getContext("2d");

      // Create and show loading message
      this.showLoadingMessage("กำลังโหลด ONNX Runtime...");

      // Load ONNX Runtime Web
      if (!window.ort) {
        console.log("Loading ONNX Runtime Web");
        const script = document.createElement("script");
        script.src = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.15.1/dist/ort.min.js";
        script.async = true;

        await new Promise((resolve, reject) => {
          script.onload = resolve;
          script.onerror = reject;
          document.head.appendChild(script);
        });
      }

      this.updateLoadingMessage("กำลังโหลดโมเดล YOLO...");
      await this.loadModel();
      this.hideLoadingMessage();
      console.log("YOLOv10 ONNX detector initialized");

      return true;
    } catch (error) {
      console.error("Error initializing YOLOv10 ONNX detector:", error);
      this.updateLoadingMessage("❌ เกิดข้อผิดพลาดในการโหลดโมเดล: " + error.message);
      return false;
    }
  }

  showLoadingMessage(message) {
    if (!this.loadingMessage) {
      this.loadingMessage = document.createElement("div");
      this.loadingMessage.className = "loading-message";
      this.loadingMessage.style.position = "absolute";
      this.loadingMessage.style.top = "50%";
      this.loadingMessage.style.left = "50%";
      this.loadingMessage.style.transform = "translate(-50%, -50%)";
      this.loadingMessage.style.backgroundColor = "rgba(0,0,0,0.7)";
      this.loadingMessage.style.color = "white";
      this.loadingMessage.style.padding = "10px 20px";
      this.loadingMessage.style.borderRadius = "5px";
      this.loadingMessage.style.zIndex = "1000";
      this.canvas.parentNode.style.position = "relative";
      this.canvas.parentNode.appendChild(this.loadingMessage);
    }
    this.loadingMessage.textContent = message;
  }

  updateLoadingMessage(message) {
    if (this.loadingMessage) {
      this.loadingMessage.textContent = message;
    } else {
      this.showLoadingMessage(message);
    }
  }

  hideLoadingMessage() {
    if (this.loadingMessage) {
      this.loadingMessage.remove();
      this.loadingMessage = null;
    }
  }

  async loadModel() {
    try {
      console.log("Loading YOLOv10 ONNX model");
      const token = document.cookie.split('; ')
        .find(row => row.startsWith('Authorization='))?.split('=')[1];

      if (!token) {
        this.updateLoadingMessage("❌ ไม่พบโทเค็นยืนยันตัวตน");
        return false;
      }

      // Fetch product names from the database first
      this.updateLoadingMessage("กำลังโหลดข้อมูลสินค้า...");
      try {
        const productResponse = await fetch('http://localhost:8001/packing/product-names', {
          headers: {
            'Authorization': 'Bearer ' + token,
          },
          cache: 'no-store'
        });

        if (!productResponse.ok) {
          console.warn(`Failed to fetch product names: ${productResponse.status} ${productResponse.statusText}`);
          // Continue with default labels if product names can't be fetched
        } else {
          const productData = await productResponse.json();
          if (productData.product_names && productData.product_names.length > 0) {
            // Use product names from the database as labels
            this.labels = productData.product_names;
            console.log(`Loaded ${this.labels.length} product names from database`);
          }
        }
      } catch (productError) {
        console.warn("Error fetching product names:", productError);
        // Continue with model loading even if product names can't be fetched
      }

      // Use relative URL to avoid hard-coding domain
      this.updateLoadingMessage("กำลังดาวน์โหลดโมเดล...");

      // Option to use relative URL
      const modelUrl = 'http://localhost:8001/packing/model';
      const modelResponse = await fetch(modelUrl, {
        headers: {
          'Authorization': 'Bearer ' + token,
        },
        // Add cache control to prevent cached responses
        cache: 'no-store'
      });

      if (!modelResponse.ok) {
        throw new Error(`Failed to fetch model: ${modelResponse.status} ${modelResponse.statusText}`);
      }

      this.updateLoadingMessage("กำลังเตรียมโมเดล...");
      const modelBuffer = await modelResponse.arrayBuffer();

      // Set more compatible ONNX Runtime options with lower memory usage
      const options = {
        executionProviders: ['wasm'],
        graphOptimizationLevel: 'basic',
        executionMode: 'sequential',
        enableCpuMemArena: false,  // Reduce memory usage
        enableMemPattern: false,   // Reduce memory usage
        wasm: {
          numThreads: 1            // Use single thread to avoid threading issues
        }
      };

      // Create ONNX Session with proper error handling
      this.updateLoadingMessage("กำลังเริ่มโมเดล...");
      try {
        this.session = await ort.InferenceSession.create(modelBuffer, options);

        // Get the input name from the model instead of hardcoding it
        if (this.session && this.session.inputNames && this.session.inputNames.length > 0) {
          this.modelInputName = this.session.inputNames[0];
          console.log(`Model input name detected: ${this.modelInputName}`);
        } else {
          // Fallback to common input names
          this.modelInputName = 'images';
          console.log("Could not detect input name, using default: 'images'");
        }

        console.log("YOLOv10 ONNX model loaded successfully");

        // If no labels have been loaded from database, use default labels
        if (!this.labels || this.labels.length === 0) {
          console.warn("No product names loaded from database, using default labels");
          // Fallback to a default list of labels
          this.labels = [
            "Arduino Mega 2560",
            "Arduino UNO WiFi Rev2",
            "Raspberry Pi Compute Module 4 IO Board",
            "Raspberry Pi 4 Power Supply",
            "SparkFun RedBoard",
            "Raspberry Pi 7\" Touchscreen Display",
            "BeagleBone Black Rev C",
            "Arduino Uno R3",
            "Thunderboard EFM32GG12",
            "MSP432 P401R LaunchPad Development Kit",
            "RPI NOIR Camera V2",
            "Power Profik Kit II",
            "Raspberry Pi 5 - 8GB RAM",
            "Arducam",
            "Raspberry Pi AI Kit",
            "Raspberry Pi Active Cooler",
            "Arducam ABS Case for IMX... 25° 24mm Camera Boards"
          ];
        }

        // Replace with your actual classes from model.names
        if (this.session.outputNames && this.session.outputNames.includes('output')) {
          console.log("Found standard output name: 'output'");
        } else {
          console.log("Output names:", this.session.outputNames);
        }

        // Generate random colors for each class
        this.labels.forEach(label => {
          this.classColors[label] = this.getRandomColor();
        });

        this.modelLoaded = true;
        return true;
      } catch (sessionError) {
        console.error("ONNX Session creation error:", sessionError);
        throw new Error(`ONNX Session creation failed: ${sessionError.message}`);
      }
    } catch (error) {
      console.error("Error loading YOLOv10 ONNX model:", error);
      this.updateLoadingMessage(`❌ Error: ${error.message}`);
      this.modelLoaded = false;
      return false;
    }
  }

  getRandomColor() {
    const letters = '0123456789ABCDEF';
    let color = '#';
    for (let i = 0; i < 6; i++) {
      color += letters[Math.floor(Math.random() * 16)];
    }
    return color;
  }

  start() {
    if (!this.modelLoaded) {
      console.error("Model not loaded yet");
      return false;
    }

    this.isRunning = true;
    this.detectFrame();
    return true;
  }

  stop() {
    this.isRunning = false;
  }

  // Preprocess the image for the ONNX model
  preprocess(imageData) {
    // Convert image to tensor
    const { width, height, data } = imageData;

    // YOLOv10 typically expects input in the format [batch, channels, height, width]
    // with pixel values normalized to [0, 1]
    const inputTensor = new Float32Array(1 * 3 * height * width);

    // YOLOv10 typically processes images in RGB format
    // Canvas gives us RGBA so we need to convert
    let offset = 0;
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        const pixelOffset = (y * width + x) * 4;

        // RGB channels - normalize from [0, 255] to [0, 1]
        inputTensor[offset] = data[pixelOffset] / 255.0;     // R
        inputTensor[offset + height * width] = data[pixelOffset + 1] / 255.0; // G
        inputTensor[offset + 2 * height * width] = data[pixelOffset + 2] / 255.0; // B

        offset++;
      }
    }

    // Create ONNX tensor
    const tensor = new ort.Tensor('float32', inputTensor, [1, 3, height, width]);

    return tensor;
  }

  async detect(imageData) {
    try {
      if (!this.session || !this.modelLoaded) {
        throw new Error("Model not loaded");
      }

      // Preprocess the image
      const inputTensor = this.preprocess(imageData);

      // Use the dynamically determined input name
      const feeds = {};
      feeds[this.modelInputName] = inputTensor;

      console.log("Running inference with input name:", this.modelInputName);
      const results = await this.session.run(feeds);

      // Extract the output - handle different output formats
      let output;
      if (results.output) {
        output = results.output;
      } else if (this.session.outputNames && this.session.outputNames.length > 0) {
        const outputName = this.session.outputNames[0];
        output = results[outputName];
      } else {
        // Last resort - try to get first value
        output = Object.values(results)[0];
      }

      if (!output) {
        console.error("Could not find output tensor in results", results);
        return [];
      }

      // Post-process the detections
      const detections = this.postprocess(output, imageData.width, imageData.height);
      return detections;
    } catch (error) {
      console.error("Error during detection:", error);
      return [];
    }
  }

  postprocess(output, imgWidth, imgHeight) {
    // Extract the raw output data
    const data = output.data;
    const [batchSize, numDetections, dimensions] = output.dims;

    const detections = [];

    // Process each detection
    for (let i = 0; i < numDetections; i++) {
      const offset = i * dimensions;

      // Extract bounding box and confidence
      const x1 = data[offset];
      const y1 = data[offset + 1];
      const x2 = data[offset + 2];
      const y2 = data[offset + 3];
      const confidence = data[offset + 4];

      // Skip low confidence detections
      if (confidence < this.confidenceThreshold) continue;

      // Find class with highest probability
      let maxClassProb = 0;
      let classIndex = 0;

      for (let j = 5; j < dimensions; j++) {
        const classProbability = data[offset + j];
        if (classProbability > maxClassProb) {
          maxClassProb = classProbability;
          classIndex = j - 5;
        }
      }

      const className = this.labels[classIndex] || `Class ${classIndex}`;

      // Add to detections
      detections.push({
        box: [x1, y1, x2, y2],
        confidence,
        class: className,
        color: this.classColors[className] || this.getRandomColor()
      });
    }

    return detections;
  }

  // Main detection loop
  async detectFrame() {
    if (!this.isRunning) return;

    if (this.video.readyState === this.video.HAVE_ENOUGH_DATA && !this.isProcessing) {
      this.isProcessing = true;

      // Adjust canvas size to match video dimensions
      this.canvas.width = this.video.videoWidth;
      this.canvas.height = this.video.videoHeight;

      // Draw video frame to canvas
      this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

      // Get image data for processing
      const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);

      // Detect objects
      const detections = await this.detect(imageData);

      // Clear canvas and redraw video frame
      this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

      // Draw detections
      this.drawDetections(detections);

      this.isProcessing = false;
    }

    // Schedule next frame
    requestAnimationFrame(() => this.detectFrame());
  }

  drawDetections(detections) {
    detections.forEach(detection => {
      const [x1, y1, x2, y2] = detection.box;
      const label = `${detection.class}: ${Math.round(detection.confidence * 100)}%`;

      // Draw bounding box
      this.ctx.strokeStyle = detection.color;
      this.ctx.lineWidth = 2;
      this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

      // Draw background for text
      this.ctx.fillStyle = detection.color;
      const textWidth = this.ctx.measureText(label).width;
      this.ctx.fillRect(x1, y1 - 20, textWidth + 10, 20);

      // Draw label
      this.ctx.fillStyle = '#FFFFFF';
      this.ctx.font = '14px Arial';
      this.ctx.fillText(label, x1 + 5, y1 - 5);
    });
  }
}

// Global detector instance
let yoloDetector = null;

// Initialize detector when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
  console.log('DOM loaded, preparing for YOLOv10 ONNX detection');

  // Create container for camera elements if it doesn't exist
  const videoElement = document.querySelector('#camera-stream');
  if (!videoElement) {
    console.error("Camera stream element not found");
    return;
  }

  // Make sure we have a canvas for detection overlay
  let canvasElement = document.querySelector('#detection-overlay');
  if (!canvasElement) {
    canvasElement = document.createElement('canvas');
    canvasElement.id = 'detection-overlay';
    canvasElement.style.position = 'absolute';
    canvasElement.style.top = '0';
    canvasElement.style.left = '0';
    canvasElement.style.width = '100%';
    canvasElement.style.height = '100%';
    canvasElement.style.zIndex = '1';

    // Create a wrapper for the video and canvas if it doesn't exist
    const wrapper = document.querySelector('#camera-wrapper');
    if (!wrapper) {
      const newWrapper = document.createElement('div');
      newWrapper.id = 'camera-wrapper';
      newWrapper.style.position = 'relative';
      newWrapper.style.width = '100%';
      newWrapper.style.maxWidth = '640px';
      newWrapper.style.margin = '0 auto';

      // Insert the wrapper
      videoElement.parentNode.insertBefore(newWrapper, videoElement);
      newWrapper.appendChild(videoElement);
      newWrapper.appendChild(canvasElement);
    } else {
      wrapper.appendChild(canvasElement);
    }
  }

  // Create or get controls container
  let controlsContainer = document.querySelector('#camera-controls');
  if (!controlsContainer) {
    controlsContainer = document.createElement('div');
    controlsContainer.id = 'camera-controls';
    controlsContainer.className = 'd-flex justify-content-center flex-wrap mt-2 gap-2';

    // Find the right place to insert controls
    const wrapper = document.querySelector('#camera-wrapper');
    if (wrapper) {
      wrapper.parentNode.insertBefore(controlsContainer, wrapper.nextSibling);
    } else {
      videoElement.parentNode.insertBefore(controlsContainer, videoElement.nextSibling);
    }
  } else {
    // Clear existing controls
    controlsContainer.innerHTML = '';
    controlsContainer.className = 'd-flex justify-content-center flex-wrap mt-2 gap-2';
  }

  // Add button to activate detection
  const activateButton = document.createElement('button');
  activateButton.textContent = 'เปิดใช้งานการตรวจจับอัตโนมัติ';
  activateButton.className = 'btn btn-primary m-1';
  activateButton.onclick = async function () {
    if (!yoloDetector) {
      activateButton.disabled = true;
      activateButton.textContent = 'กำลังโหลดโมเดล...';

      // Initialize detector
      yoloDetector = new YOLODetector();
      const initialized = await yoloDetector.initialize(videoElement, canvasElement);

      activateButton.disabled = false;

      if (!initialized) {
        activateButton.textContent = 'ลองโหลดโมเดลอีกครั้ง';
        return;
      }

      // Start detection
      yoloDetector.start();
      activateButton.textContent = 'ปิดการตรวจจับอัตโนมัติ';
    } else {
      if (yoloDetector.isRunning) {
        yoloDetector.stop();
        activateButton.textContent = 'เปิดใช้งานการตรวจจับอัตโนมัติ';
      } else {
        yoloDetector.start();
        activateButton.textContent = 'ปิดการตรวจจับอัตโนมัติ';
      }
    }
  };

  // Add button to capture image
  const captureButton = document.createElement('button');
  captureButton.textContent = 'จับภาพ';
  captureButton.className = 'btn btn-success m-1';
  captureButton.onclick = function () {
    // Implement capture functionality here
    // You can access the current canvas content or take a new snapshot
    const dataUrl = canvasElement.toDataURL('image/jpeg');

    // Create a temporary link to download the image
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = `capture-${new Date().toISOString()}.jpg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Add buttons to the controls container
  controlsContainer.appendChild(activateButton);
  controlsContainer.appendChild(captureButton);

  // Apply styles to camera and canvas
  videoElement.style.width = '100%';
  videoElement.style.maxWidth = '640px';
  videoElement.style.height = 'auto';

  // Add responsive CSS
  const style = document.createElement('style');
  style.textContent = `
    #camera-wrapper {
      position: relative;
      width: 100%;
      max-width: 640px;
      margin: 0 auto;
      overflow: hidden;
      border-radius: 8px;
      box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    #detection-overlay {
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 1;
    }
    
    #camera-controls {
      margin-top: 10px;
      text-align: center;
    }
    
    .loading-message {
      font-weight: bold;
    }
    
    @media (max-width: 768px) {
      #camera-wrapper {
        max-width: 100%;
      }
    }
  `;
  document.head.appendChild(style);
});