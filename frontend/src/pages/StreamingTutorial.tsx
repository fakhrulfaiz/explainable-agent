import { useState } from "react";

export default function Chat() {
  const [messages, setMessages] = useState<string[]>([]);
  const [imageSrc, setImageSrc] = useState<string | null>(null);

  const sendRequest = async () => {
    const response = await fetch("http://localhost:8000/stream/chat", {
      method: "POST",
    });
    const reader = response.body?.getReader();
    if (!reader) {
      console.error('Response body is null');
      return;
    }
    const decoder = new TextDecoder();

    let buffer = "";
    let b64data = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      let lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.trim()) {
          const obj = JSON.parse(line);

          if (obj.type === "text") {
            setMessages((prev) => [...prev, obj.data]);
          }
          else if (obj.type === "image_chunk") {
            b64data += obj.data;
          }
          else if (obj.type === "done") {
            // convert base64 back to Blob
            const byteCharacters = atob(b64data);
            const byteNumbers = Array.from(byteCharacters).map(c => c.charCodeAt(0));
            const blob = new Blob([new Uint8Array(byteNumbers)], { type: "image/jpeg" });
            const url = URL.createObjectURL(blob);
            setImageSrc(url);
          }
        }
      }
    }
  };

  return (
    <div style={{
      padding: "20px",
      minHeight: "100vh",
      backgroundColor: "#ffffff",
      color: "#000000"
    }}>
      <h1 style={{ 
        marginBottom: "20px",
        color: "#333333"
      }}>
        Streaming Tutorial
      </h1>
      
      <button 
        onClick={sendRequest}
        style={{
          padding: "12px 24px",
          fontSize: "16px",
          backgroundColor: "#007bff",
          color: "white",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          marginBottom: "20px"
        }}
        onMouseOver={(e) => (e.target as HTMLButtonElement).style.backgroundColor = "#0056b3"}
        onMouseOut={(e) => (e.target as HTMLButtonElement).style.backgroundColor = "#007bff"}
      >
        Ask for Cat
      </button>
      
      <div style={{ 
        marginTop: 20,
        padding: "20px",
        backgroundColor: "#f8f9fa",
        borderRadius: "8px",
        border: "1px solid #dee2e6"
      }}>
        {messages.length === 0 && (
          <p style={{ color: "#6c757d", fontStyle: "italic" }}>
            Click the button to start streaming...
          </p>
        )}
        {messages.map((msg, idx) => (
          <div 
            key={idx} 
            style={{ 
              marginBottom: "10px",
              padding: "10px",
              backgroundColor: "#ffffff",
              borderRadius: "4px",
              border: "1px solid #e9ecef"
            }}
          >
            <b style={{ color: "#495057" }}>Assistant:</b> 
            <span style={{ color: "#212529", marginLeft: "8px" }}>{msg}</span>
          </div>
        ))}
        {imageSrc && (
          <div style={{ marginTop: "20px", textAlign: "center" }}>
            <img 
              src={imageSrc} 
              alt="Cat" 
              style={{ 
                maxWidth: "300px", 
                borderRadius: "8px",
                border: "2px solid #dee2e6",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
              }} 
            />
          </div>
        )}
      </div>
    </div>
  );
}
