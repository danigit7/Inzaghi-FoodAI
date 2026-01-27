import React, { useState, useRef, useEffect } from 'react';
import { Send, User, Bot, MapPin, DollarSign, Star, Sparkles } from 'lucide-react';


const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isThinking]);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const userMsg = { id: Date.now(), text: input, sender: 'user' };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setIsThinking(true); // Start thinking animation

    // Simulate thinking delay (2-3 seconds)
    setTimeout(async () => {
      try {
        const response = await fetch('/chat', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ message: userMsg.text, session_id: sessionId }),
        });

        const data = await response.json();
        
        if (data.session_id) {
          setSessionId(data.session_id);
        }
        
        const botMsg = { 
          id: Date.now() + 1, 
          text: data.response, 
          sender: 'bot',
          suggestions: data.suggestions 
        };
        
        setIsThinking(false); // Stop thinking
        setMessages(prev => [...prev, botMsg]);
      } catch (error) {
        console.error("Error sending message:", error);
        setIsThinking(false);
        setMessages(prev => [...prev, { id: Date.now() + 1, text: "Sorry, I'm having trouble connecting to the server.", sender: 'bot' }]);
      } finally {
        setIsLoading(false);
      }
    }, 2500); // 2.5s delay
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      sendMessage();
    }
  };

  return (
    <div className="w-full max-w-3xl h-[85vh] flex flex-col glass-panel rounded-3xl shadow-2xl overflow-hidden relative animate-fade-in">
      
      {/* Header */}
      <div className="p-6 border-b border-[rgba(255,255,255,0.05)] flex items-center justify-between bg-[rgba(15,17,26,0.6)] backdrop-blur-md z-10">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 p-[2px] animate-pulse-glow">
              <div className="w-full h-full rounded-full bg-[#1e2130] flex items-center justify-center overflow-hidden">
                <img src="/INZAGHI.png" alt="Inzaghi" className="w-full h-full object-cover" />
              </div>
            </div>
            <div className="absolute bottom-0 right-0 w-3 h-3 bg-green-400 rounded-full border-2 border-[#1e2130]"></div>
          </div>
          <div>
            <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-teal-300 font-heading tracking-wide">
              Inzaghi
            </h1>
            <p className="text-xs text-gray-400 flex items-center gap-1 font-body">
              <Sparkles size={10} className="text-yellow-400" />
              Peshawar Foodie AI
            </p>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent relative">
        
        {/* Background Watermark Logo (ChatGPT Style) */}
        {messages.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
            <img 
              src="/INZAGHI.png" 
              alt="Inzaghi Watermark" 
              className="w-48 h-48 md:w-64 md:h-64 object-contain opacity-[0.03] filter grayscale invert brightness-200" 
            />
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}>
            <div className={`flex max-w-[85%] ${msg.sender === 'user' ? 'flex-row-reverse' : 'flex-row'} gap-3`}>
              
              {/* Avatar */}
              <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 shadow-lg overflow-hidden
                ${msg.sender === 'user' 
                  ? 'bg-gradient-to-br from-gray-600 to-gray-800' 
                  : 'bg-transparent'}`}>
                {msg.sender === 'user' ? (
                  <User size={14} className="text-white" />
                ) : (
                  <img src="/INZAGHI.png" alt="Bot" className="w-full h-full object-cover" />
                )}
              </div>
              
              {/* Message Bubble */}
              <div className={`p-4 rounded-2xl shadow-md backdrop-blur-sm transition-all duration-300 hover:shadow-lg ${
                msg.sender === 'user' 
                  ? 'bg-[#2a2f45] text-white rounded-tr-none border border-[rgba(255,255,255,0.05)]' 
                  : 'bg-gradient-to-br from-[#1e2130] to-[#25293c] text-gray-100 rounded-tl-none border border-[rgba(76,139,245,0.2)]'
              }`}>
                <p className="whitespace-pre-wrap leading-relaxed text-sm md:text-base">{msg.text}</p>
                
                {/* Suggestions Cards */}
                {msg.suggestions && msg.suggestions.length > 0 && (
                  <div className="mt-4 grid gap-3">
                    {msg.suggestions.map((rest) => (
                      <div key={rest.id} className="bg-[#151722] p-4 rounded-xl border border-[rgba(255,255,255,0.05)] hover:border-blue-500/50 transition-colors group">
                        <div className="flex justify-between items-start">
                          <h3 className="font-bold text-blue-300 group-hover:text-blue-200 transition-colors">{rest.name}</h3>
                          <span className="flex items-center text-xs bg-[#2a2f45] px-2 py-1 rounded-full text-yellow-400">
                            <Star size={10} className="mr-1 fill-current" /> {rest.rating || 'N/A'}
                          </span>
                        </div>
                        
                        <div className="flex items-center text-gray-400 mt-2 text-xs">
                          <DollarSign size={12} className="text-green-400 mr-1" />
                          <span className="mr-3">{rest.budget || 'N/A'}</span>
                          <MapPin size={12} className="text-red-400 mr-1" />
                          <span className="truncate max-w-[150px]">{rest.location}</span>
                        </div>
                        
                        {rest.deals && rest.deals.length > 0 && (
                           <div className="mt-2 text-xs text-teal-300 bg-teal-900/20 px-2 py-1 rounded border border-teal-900/30">
                             🎉 {rest.deals[0]}
                           </div>
                        )}

                        <div className="mt-3 flex flex-wrap gap-1">
                          {rest.cuisine.slice(0, 3).map((c, idx) => (
                            <span key={idx} className="px-2 py-0.5 bg-[#2a2f45] text-gray-300 rounded-full text-[10px] border border-[rgba(255,255,255,0.05)]">
                              {c}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* Thinking State */}
        {isThinking && (
          <div className="flex justify-start animate-slide-up">
            <div className="flex flex-row gap-3">
              <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-1 overflow-hidden">
                <img src="/INZAGHI.png" alt="Thinking..." className="w-full h-full object-cover" />
              </div>
              <div className="bg-[#1e2130] p-4 rounded-2xl rounded-tl-none border border-[rgba(76,139,245,0.2)] flex items-center gap-3">
                <div className="gemini-loader">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="text-xs text-blue-300 font-medium animate-pulse">{['Soch raha hoon…', 'Let me think…', 'Hmm… taste ke hisaab se…'][Math.floor(Math.random() * 3)]}</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-6 bg-gradient-to-t from-[#0f111a] to-transparent">
        <div className="flex items-center bg-[#1e2130] rounded-full px-2 py-2 border border-[rgba(255,255,255,0.1)] shadow-lg focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500/50 transition-all duration-300 hover:border-[rgba(255,255,255,0.2)]">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask Inzaghi about food..."
            className="flex-1 bg-transparent outline-none text-gray-200 placeholder-gray-500 px-4 py-2"
            disabled={isLoading}
          />
          <button 
            onClick={sendMessage}
            disabled={isLoading || !input.trim()}
            className={`p-3 rounded-full flex items-center justify-center transition-all duration-300 ${
              isLoading || !input.trim() 
                ? 'bg-[#2a2f45] text-gray-500 cursor-not-allowed' 
                : 'bg-gradient-to-r from-blue-600 to-violet-600 text-white hover:shadow-[0_0_15px_rgba(76,139,245,0.5)] transform hover:scale-105'
            }`}
          >
            <Send size={18} />
          </button>
        </div>
        <p className="text-center text-[10px] text-gray-600 mt-2">
          {/* AI can make mistakes. Check important info. */}
        </p>
      </div>
    </div>
  );
};

export default ChatInterface;
