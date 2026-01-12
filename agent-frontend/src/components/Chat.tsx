import { useState, useRef, useEffect } from 'react';
import { Send, User, Loader2 } from 'lucide-react';

type Message = {
  id: string;
  text: string;
  sender: 'user' | 'bot';
  timestamp: Date;
};

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      text: 'Olá! Sou o Rito, seu assistente bancário. Como posso ajudar com você hoje?',
      sender: 'bot',
      timestamp: new Date(),
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    const userInput = input;
    setInput('');
    setIsLoading(true);

    try {
      const response = await fetch(`http://localhost:8000/chat/message?query=${encodeURIComponent(userInput)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Erro na requisição');
      }

      const data = await response.json();
      
      const botMsg: Message = {
        id: (Date.now() + 1).toString(),
        text: data.response || 'Desculpe, não consegui processar sua mensagem.',
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (error) {
      console.error('Erro ao enviar mensagem:', error);
      const errorMsg: Message = {
        id: (Date.now() + 1).toString(),
        text: 'Desculpe, ocorreu um erro ao processar sua mensagem. Tente novamente.',
        sender: 'bot',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSend();
  };

  return (
    <div className="flex flex-col h-150 w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-200">
      
      <div className="bg-bank-blue p-4 flex items-center gap-3 shadow-md">
        <div className="relative">
          <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center overflow-hidden border-2 border-green-900">

            <img src="rito.png" alt="Rito" />
          </div>
          <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-900 rounded-full border-2 border-white"></span>
        </div>
        <div>
          <h1 className="text-white font-bold text-lg tracking-wide">Rito</h1>
          <p className="text-blue-500 text flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-green-900 rounded-full animate-pulse"></span>
            Online agora
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex items-end gap-2 max-w-[80%]`}>
              {msg.sender === 'bot' && (
                <div className="w-6 h-6 rounded-full bg-white flex items-center justify-center shrink-0 overflow-hidden">
                  <img src="rito.png" alt="Rito" className="w-full h-full object-cover" />
                </div>
              )}
              
              <div
                className={`p-3 rounded-2xl text-sm shadow-sm ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-br-none'
                    : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
                }`}
              >
                {msg.text}
              </div>

              {msg.sender === 'user' && (
                <div className="w-6 h-6 rounded-full bg-gray-300 flex items-center justify-center shrink-0">
                  <User size={14} className="text-gray-600" />
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-white p-3 rounded-2xl rounded-bl-none border border-gray-200 shadow-sm flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
              <span className="text-xs text-gray-500">Rito está digitando...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-4 bg-white border-t border-gray-100">
        <div className="flex items-center gap-2 bg-gray-100 rounded-full px-4 py-2 border border-gray-200 focus-within:border-blue-400 focus-within:ring-2 focus-within:ring-blue-100 transition-all">
          <input
            type="text"
            className="flex-1 bg-transparent outline-none text-gray-700 placeholder-gray-400"
            placeholder="Digite sua mensagem..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="p-2 bg-blue-600 rounded-full text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send size={18} />
          </button>
        </div>
        <p className="text-center text-[10px] text-gray-400 mt-2">
          Rito Bank AI • Ambiente Seguro
        </p>
      </div>
    </div>
  );
}