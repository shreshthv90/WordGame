import React, { useState, useEffect, useCallback, useRef } from 'react';
import './App.css';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './components/ui/card';
import { Badge } from './components/ui/badge';
import { Separator } from './components/ui/separator';
import { Users, Trophy, Clock, Zap, Wifi, WifiOff } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');

function App() {
  const [gameState, setGameState] = useState('menu'); // 'menu', 'lobby', 'playing', 'profile'
  const [roomCode, setRoomCode] = useState('');
  const [playerName, setPlayerName] = useState('');
  const [currentUser, setCurrentUser] = useState(null); // Authenticated user data
  const [sessionToken, setSessionToken] = useState(null); // Session token for API calls
  const [selectedWordLength, setSelectedWordLength] = useState(3); // New: word length setting
  const [selectedTimerMinutes, setSelectedTimerMinutes] = useState(4); // New: timer setting (2, 4, or 6 minutes)
  const [gameWordLength, setGameWordLength] = useState(3); // Current game's word length requirement
  const [gameTimerMinutes, setGameTimerMinutes] = useState(4); // Current game's timer setting
  const [timeRemaining, setTimeRemaining] = useState(0); // Time remaining in seconds
  const [showRules, setShowRules] = useState(false); // Show/hide rules section
  const [showSuccessAnimation, setShowSuccessAnimation] = useState(false); // Success animation state
  const [successWord, setSuccessWord] = useState(''); // Word that was accepted
  const [players, setPlayers] = useState([]);
  const [lettersOnTable, setLettersOnTable] = useState([]);
  const [selectedLetters, setSelectedLetters] = useState([]);
  const [currentWord, setCurrentWord] = useState('');
  const [messages, setMessages] = useState([]);
  const [gameStarted, setGameStarted] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  
  const wsRef = useRef(null);

  const addMessage = (text) => {
    setMessages(prev => [...prev, { text, timestamp: Date.now() }].slice(-10));
  };

  const formatTime = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const triggerSuccessAnimation = (word) => {
    setSuccessWord(word);
    setShowSuccessAnimation(true);
    setTimeout(() => {
      setShowSuccessAnimation(false);
    }, 2000); // Hide after 2 seconds
  };

  // Authentication Functions
  const handleLogin = () => {
    const redirectUrl = encodeURIComponent(window.location.origin + '/#/profile');
    window.location.href = `https://auth.emergentagent.com/?redirect=${redirectUrl}`;
  };

  const handleLogout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
      setCurrentUser(null);
      setSessionToken(null);
      setPlayerName('');
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const checkAuthStatus = async () => {
    try {
      const response = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setCurrentUser(response.data);
      setPlayerName(response.data.name);
      return response.data;
    } catch (error) {
      setCurrentUser(null);
      setSessionToken(null);
      return null;
    }
  };

  // Handle OAuth redirect with session ID
  useEffect(() => {
    const handleAuthRedirect = async () => {
      const hash = window.location.hash;
      const sessionMatch = hash.match(/session_id=([^&]+)/);
      
      if (sessionMatch) {
        const sessionId = sessionMatch[1];
        try {
          const response = await axios.post(`${API}/auth/profile?session_id=${sessionId}`, {}, {
            withCredentials: true
          });
          
          if (response.data.success) {
            setCurrentUser(response.data.user);
            setPlayerName(response.data.user.name);
            setGameState('profile');
            
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        } catch (error) {
          console.error('Authentication error:', error);
        }
      } else {
        // Check if already authenticated
        await checkAuthStatus();
      }
    };

    handleAuthRedirect();
  }, []);

  // Scrabble letter scores for rules display
  const letterScores = {
    1: ['A', 'E', 'I', 'O', 'U', 'L', 'N', 'S', 'T', 'R'],
    2: ['D', 'G'],
    3: ['B', 'C', 'M', 'P'],
    4: ['F', 'H', 'V', 'W', 'Y'],
    5: ['K'],
    8: ['J', 'X'],
    10: ['Q', 'Z']
  };

  const connectWebSocket = useCallback((code) => {
    const wsUrl = `${WS_URL}/api/ws/${code}`;
    console.log('Connecting to WebSocket:', wsUrl);
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setConnectionStatus('connected');
      console.log('Connected to WebSocket');
      addMessage('Connected to game server!');
    };
    
    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };
    
    ws.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket connection closed');
      addMessage('Disconnected from game server');
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
      addMessage('Connection error occurred');
    };
    
    wsRef.current = ws;
  }, []);

  const handleWebSocketMessage = (message) => {
    console.log('Received message:', message);
    
    switch (message.type) {
      case 'player_joined':
        setPlayers(message.players);
        addMessage(`${message.player_name} joined the game`);
        break;
        
      case 'player_left':
        setPlayers(message.players);
        addMessage(`${message.player_name} left the game`);
        break;
        
      case 'game_state':
        setLettersOnTable(message.letters);
        setPlayers(message.players);
        setGameStarted(message.game_started);
        setGameWordLength(message.word_length || 3); // Set game's word length requirement
        setGameTimerMinutes(message.timer_minutes || 4); // Set game's timer setting
        setTimeRemaining(message.time_remaining || 0); // Set current time remaining
        break;
        
      case 'game_started':
        setGameStarted(true);
        setGameState('playing');
        setGameTimerMinutes(message.timer_minutes || 4);
        setTimeRemaining(message.time_remaining || 0);
        addMessage('Game started! Letters will appear every 4 seconds.');
        break;
        
      case 'new_letter':
        setLettersOnTable(message.letters);
        addMessage(`New letter appeared: ${message.letter}`);
        break;
        
      case 'word_accepted':
        setPlayers(message.players);
        setLettersOnTable(message.letters);
        setSelectedLetters([]);
        setCurrentWord('');
        triggerSuccessAnimation(message.word); // Trigger success animation
        addMessage(`${message.player} scored ${message.score} points with "${message.word}"!`);
        break;
        
      case 'word_rejected':
        addMessage(`Word "${message.word}" was rejected: ${message.reason}`);
        setSelectedLetters([]);
        setCurrentWord('');
        break;
        
      case 'timer_update':
        setTimeRemaining(message.time_remaining || 0);
        break;
        
      case 'game_ended':
        setGameStarted(false);
        const winner = message.final_scores?.reduce((prev, current) => 
          prev.score > current.score ? prev : current
        );
        const reason = message.reason === 'time_up' ? 'Time is up!' : 'Game ended!';
        if (winner) {
          addMessage(`${reason} Winner: ${winner.name} with ${winner.score} points!`);
        } else {
          addMessage(reason);
        }
        break;
        
      default:
        console.log('Unknown message type:', message.type);
    }
  };

  const createRoom = async () => {
    try {
      const response = await axios.post(`${API}/create-room`, {
        word_length: selectedWordLength,
        timer_minutes: selectedTimerMinutes
      });
      const data = response.data;
      setRoomCode(data.room_code);
      setGameWordLength(selectedWordLength);
      setGameTimerMinutes(selectedTimerMinutes);
      setGameState('lobby');
      
      // Connect to WebSocket
      connectWebSocket(data.room_code);
      addMessage(`Room created! Word length: ${selectedWordLength} letters, Timer: ${selectedTimerMinutes} minutes`);
    } catch (error) {
      console.error('Error creating room:', error);
      addMessage('Failed to create room');
    }
  };

  const joinRoom = () => {
    if (roomCode && playerName) {
      setGameState('lobby');
      connectWebSocket(roomCode);
    }
  };

  const joinGame = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && playerName) {
      wsRef.current.send(JSON.stringify({
        type: 'join',
        player_name: playerName,
        session_token: sessionToken // Include session token for authentication
      }));
    }
  };

  const startGame = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'start_game'
      }));
    }
  };

  const selectLetter = (letterId, letter) => {
    if (selectedLetters.find(l => l.id === letterId)) {
      // Deselect letter
      setSelectedLetters(prev => prev.filter(l => l.id !== letterId));
      setCurrentWord(prev => {
        const letterIndex = selectedLetters.findIndex(l => l.id === letterId);
        const wordArray = prev.split('');
        wordArray.splice(letterIndex, 1);
        return wordArray.join('');
      });
    } else {
      // Select letter
      setSelectedLetters(prev => [...prev, { id: letterId, letter }]);
      setCurrentWord(prev => prev + letter);
    }
  };

  const submitWord = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && currentWord.length === gameWordLength) {
      wsRef.current.send(JSON.stringify({
        type: 'submit_word',
        word: currentWord,
        selected_letter_ids: selectedLetters.map(l => l.id)
      }));
    }
  };

  const clearSelection = () => {
    setSelectedLetters([]);
    setCurrentWord('');
  };

  // Auto-join game when entering lobby
  useEffect(() => {
    if (gameState === 'lobby' && wsRef.current && playerName && connectionStatus === 'connected') {
      const timer = setTimeout(() => {
        joinGame();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [gameState, playerName, connectionStatus]);

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  if (gameState === 'menu') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-400 via-blue-500 to-indigo-600 relative overflow-hidden">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-10 left-10 w-32 h-32 bg-orange-300 rounded-full blur-xl animate-pulse"></div>
          <div className="absolute top-32 right-20 w-24 h-24 bg-yellow-300 rounded-full blur-lg animate-bounce"></div>
          <div className="absolute bottom-20 left-1/4 w-40 h-40 bg-orange-400 rounded-full blur-2xl animate-pulse delay-1000"></div>
          <div className="absolute bottom-32 right-1/3 w-28 h-28 bg-amber-300 rounded-full blur-xl animate-bounce delay-500"></div>
        </div>
        
        <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
          <Card className="w-full max-w-md shadow-2xl border-0 bg-white/95 backdrop-blur-lg rounded-3xl game-container overflow-hidden">
            <div className="bg-gradient-to-r from-orange-500 to-amber-500 p-6 text-center">
              <div className="mx-auto w-24 h-24 bg-white rounded-3xl flex items-center justify-center mb-4 shadow-lg transform hover:scale-105 transition-transform">
                <img 
                  src="https://customer-assets.emergentagent.com/job_wordplay-hub-2/artifacts/4qngir0x_nikki%20logo.png" 
                  alt="Nikki's Logo" 
                  className="w-20 h-20 object-cover rounded-2xl"
                />
              </div>
              <h1 className="text-4xl font-black text-white mb-2 drop-shadow-lg">
                Nikki's Word Rush
              </h1>
              <div className="bg-white/20 rounded-full px-4 py-1 inline-block">
                <span className="text-white/90 text-sm font-semibold">Competitive Word Gaming</span>
              </div>
            </div>

            <CardContent className="p-6 space-y-6">
              {/* Player Name Input */}
              <div className="space-y-3">
                <label className="text-lg font-bold text-gray-800 flex items-center gap-2">
                  <div className="w-3 h-3 bg-gradient-to-r from-orange-500 to-amber-500 rounded-full"></div>
                  Your Name
                </label>
                <Input
                  placeholder="Enter your player name"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  className="text-lg p-4 border-3 border-blue-200 focus:border-orange-400 rounded-2xl font-semibold bg-blue-50/50 placeholder:text-gray-500"
                />
              </div>

              {/* Game Settings */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-4 border-2 border-blue-200">
                <h3 className="text-lg font-black text-gray-800 mb-4 flex items-center gap-2">
                  <div className="w-3 h-3 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"></div>
                  Game Settings
                </h3>
                
                <div className="space-y-4">
                  <div className="space-y-3">
                    <label className="text-sm font-bold text-gray-700">Word Length:</label>
                    <div className="grid grid-cols-4 gap-2">
                      {[3, 4, 5, 6].map(length => (
                        <button
                          key={length}
                          onClick={() => setSelectedWordLength(length)}
                          className={`p-3 rounded-xl font-black text-sm transition-all duration-200 transform hover:scale-105 shadow-lg ${
                            selectedWordLength === length
                              ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white scale-105 shadow-xl'
                              : 'bg-white text-gray-700 hover:bg-orange-50 border-2 border-orange-200'
                          }`}
                        >
                          {length}
                        </button>
                      ))}
                    </div>
                    <div className="text-center">
                      <span className="text-xs bg-white/60 px-3 py-1 rounded-full text-gray-600 font-semibold">
                        All words must be exactly {selectedWordLength} letters long
                      </span>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-sm font-bold text-gray-700">Game Timer:</label>
                    <div className="grid grid-cols-3 gap-2">
                      {[2, 4, 6].map(minutes => (
                        <button
                          key={minutes}
                          onClick={() => setSelectedTimerMinutes(minutes)}
                          className={`p-3 rounded-xl font-black text-sm transition-all duration-200 transform hover:scale-105 shadow-lg ${
                            selectedTimerMinutes === minutes
                              ? 'bg-gradient-to-r from-blue-500 to-indigo-500 text-white scale-105 shadow-xl'
                              : 'bg-white text-gray-700 hover:bg-blue-50 border-2 border-blue-200'
                          }`}
                        >
                          {minutes}m
                        </button>
                      ))}
                    </div>
                    <div className="text-center">
                      <span className="text-xs bg-white/60 px-3 py-1 rounded-full text-gray-600 font-semibold">
                        Battle ends after {selectedTimerMinutes} minutes
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-4">
                <Button 
                  onClick={createRoom} 
                  className="w-full bg-gradient-to-r from-orange-500 via-amber-500 to-yellow-500 hover:from-orange-600 hover:via-amber-600 hover:to-yellow-600 text-white font-black py-4 text-lg rounded-2xl shadow-xl transform hover:scale-105 transition-all duration-200"
                  disabled={!playerName}
                >
                  🎮 Start New Battle
                </Button>
                
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <Separator className="w-full bg-gradient-to-r from-transparent via-gray-300 to-transparent" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-4 py-1 text-gray-500 font-bold rounded-full">Or Join Battle</span>
                  </div>
                </div>
                
                <div className="space-y-3">
                  <Input
                    placeholder="BATTLE CODE"
                    value={roomCode}
                    onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                    className="text-center text-xl font-black tracking-wider border-3 border-blue-200 focus:border-blue-400 rounded-2xl p-4 bg-blue-50/50"
                  />
                  <Button 
                    onClick={joinRoom} 
                    variant="outline" 
                    className="w-full border-3 border-blue-500 text-blue-600 hover:bg-blue-500 hover:text-white font-black py-4 text-lg rounded-2xl shadow-lg transform hover:scale-105 transition-all duration-200"
                    disabled={!playerName || !roomCode}
                  >
                    ⚔️ Join Battle
                  </Button>
                </div>
              </div>

              {/* Rules Section */}
              <div className="border-t-2 border-gray-200 pt-4">
                <Button
                  variant="ghost"
                  onClick={() => setShowRules(!showRules)}
                  className="w-full text-sm text-gray-600 hover:text-gray-800 font-bold bg-gray-50 hover:bg-gray-100 rounded-xl p-3"
                >
                  {showRules ? '📋 Hide' : '📋 Show'} Battle Rules & Points
                </Button>
                
                {showRules && (
                  <div className="mt-4 p-4 bg-gradient-to-r from-gray-50 to-blue-50 rounded-2xl border-2 border-gray-200">
                    <h3 className="font-black text-gray-800 mb-3 text-center">⚔️ Battle Rules</h3>
                    <div className="grid grid-cols-1 gap-3 text-xs">
                      <div className="bg-white rounded-xl p-3 shadow-sm">
                        <h4 className="font-bold text-gray-800 mb-2">Letter Points:</h4>
                        <div className="grid grid-cols-2 gap-1">
                          {Object.entries(letterScores).map(([points, letters]) => (
                            <div key={points} className="flex justify-between items-center">
                              <span className="font-bold text-orange-600">{points}pt:</span>
                              <span className="font-mono text-gray-700 text-right text-xs">{letters.slice(0,5).join('')}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="bg-white rounded-xl p-3 shadow-sm">
                        <h4 className="font-bold text-gray-800 mb-2">Battle Strategy:</h4>
                        <ul className="text-xs text-gray-600 space-y-1">
                          <li>• First to submit valid word wins the letters</li>
                          <li>• Higher point letters = higher scores</li>
                          <li>• Battle ends when timer expires</li>
                          <li>• Most points wins the battle!</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (gameState === 'lobby') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-400 via-indigo-500 to-purple-600 relative overflow-hidden">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-16 right-16 w-36 h-36 bg-orange-300 rounded-full blur-2xl animate-pulse"></div>
          <div className="absolute bottom-16 left-16 w-28 h-28 bg-yellow-300 rounded-full blur-xl animate-bounce delay-700"></div>
        </div>
        
        <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
          <Card className="w-full max-w-lg shadow-2xl border-0 bg-white/95 backdrop-blur-lg rounded-3xl game-container overflow-hidden">
            
            {/* Header */}
            <div className="bg-gradient-to-r from-orange-500 to-amber-500 p-6 text-center">
              <div className="mx-auto w-20 h-20 bg-white rounded-3xl flex items-center justify-center mb-4 shadow-xl transform hover:scale-105 transition-transform">
                <img 
                  src="https://customer-assets.emergentagent.com/job_wordplay-hub-2/artifacts/4qngir0x_nikki%20logo.png" 
                  alt="Nikki's Logo" 
                  className="w-16 h-16 object-cover rounded-2xl"
                />
              </div>
              <h1 className="text-3xl font-black text-white mb-2 drop-shadow-lg">
                Battle Room Ready
              </h1>
              <div className="bg-white/20 rounded-full px-4 py-2 inline-block">
                <span className="text-white font-black text-lg tracking-wider">{roomCode}</span>
              </div>
            </div>

            <CardContent className="p-6 space-y-6">
              
              {/* Battle Settings */}
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl p-5 border-2 border-blue-200">
                <h3 className="text-lg font-black text-gray-800 mb-4 flex items-center gap-2">
                  <div className="w-3 h-3 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"></div>
                  Battle Configuration
                </h3>
                
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-white rounded-xl p-4 shadow-sm border-2 border-orange-200">
                    <div className="text-orange-600 font-black text-sm">WORD LENGTH</div>
                    <div className="text-2xl font-black text-gray-800">{gameWordLength}</div>
                    <div className="text-xs text-gray-600 font-semibold">letters required</div>
                  </div>
                  <div className="bg-white rounded-xl p-4 shadow-sm border-2 border-blue-200">
                    <div className="text-blue-600 font-black text-sm">BATTLE TIME</div>
                    <div className="text-2xl font-black text-gray-800">{gameTimerMinutes}</div>
                    <div className="text-xs text-gray-600 font-semibold">minutes</div>
                  </div>
                </div>
              </div>

              {/* Warriors (Players) */}
              <div className="space-y-4">
                <h3 className="text-lg font-black text-gray-800 flex items-center gap-2">
                  <div className="w-3 h-3 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full"></div>
                  Warriors in Battle ({players.length})
                </h3>
                
                <div className="space-y-3">
                  {players.map((player, index) => (
                    <div key={index} className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-xl p-4 border-2 border-purple-200 shadow-sm">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center shadow-lg">
                          <span className="text-white font-black text-sm">⚔️</span>
                        </div>
                        <div>
                          <div className="font-black text-gray-800">{player.name}</div>
                          <div className="text-sm text-purple-600 font-semibold">Ready for battle</div>
                        </div>
                      </div>
                    </div>
                  ))}
                  
                  {players.length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <div className="text-4xl mb-2">⏳</div>
                      <div className="font-semibold">Waiting for warriors to join...</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="space-y-4">
                {!gameStarted && (
                  <button 
                    onClick={startGame} 
                    disabled={players.length < 1}
                    className={`w-full py-4 rounded-2xl font-black text-lg shadow-xl transition-all duration-200 transform ${
                      players.length >= 1
                        ? 'bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 text-white hover:scale-105 hover:shadow-2xl'
                        : 'bg-gray-400 text-gray-600 cursor-not-allowed'
                    }`}
                  >
                    ⚔️ START BATTLE
                  </button>
                )}
                
                <button 
                  onClick={() => {
                    setGameState('menu');
                    setRoomCode('');
                    if (wsRef.current) {
                      wsRef.current.close();
                    }
                  }}
                  className="w-full py-3 rounded-2xl font-black text-sm bg-gradient-to-r from-red-500 to-pink-500 text-white shadow-lg hover:scale-105 transition-all duration-200"
                >
                  🚪 LEAVE ROOM
                </button>
              </div>

              {/* Connection Status */}
              <div className="text-center">
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-semibold ${
                  connectionStatus === 'connected' 
                    ? 'bg-green-100 text-green-700 border-2 border-green-300' 
                    : 'bg-red-100 text-red-700 border-2 border-red-300'
                }`}>
                  {connectionStatus === 'connected' ? (
                    <>
                      <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                      Battle Ready
                    </>
                  ) : (
                    <>
                      <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                      Reconnecting...
                    </>
                  )}
                </div>
              </div>
              
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  if (gameState === 'playing') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-400 via-indigo-500 to-purple-600 p-4 relative overflow-hidden">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-5">
          <div className="absolute top-20 left-20 w-40 h-40 bg-orange-300 rounded-full blur-2xl animate-pulse"></div>
          <div className="absolute bottom-20 right-20 w-32 h-32 bg-yellow-300 rounded-full blur-xl animate-bounce delay-1000"></div>
        </div>
        
        <div className="relative z-10 max-w-6xl mx-auto space-y-4">
          
          {/* Success Animation - Positioned on the right side */}
          {showSuccessAnimation && (
            <div className="fixed top-4 right-4 z-50 animate-bounce">
              <div className="bg-gradient-to-r from-green-400 to-emerald-500 rounded-2xl p-4 shadow-2xl border-3 border-white flex items-center gap-3">
                <img 
                  src="https://customer-assets.emergentagent.com/job_wordplay-hub-2/artifacts/4qngir0x_nikki%20logo.png" 
                  alt="Success!" 
                  className="w-12 h-12 object-cover rounded-xl"
                />
                <div className="text-white text-3xl drop-shadow-lg">👍</div>
                <div className="text-white font-black text-lg drop-shadow-lg">{successWord}!</div>
              </div>
            </div>
          )}

          {/* Header */}
          <Card className="bg-gradient-to-r from-orange-500 to-amber-500 shadow-2xl border-0 rounded-2xl overflow-hidden game-container">
            <CardContent className="p-4">
              <div className="flex justify-between items-center text-white">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 bg-white rounded-2xl flex items-center justify-center shadow-lg">
                    <img 
                      src="https://customer-assets.emergentagent.com/job_wordplay-hub-2/artifacts/4qngir0x_nikki%20logo.png" 
                      alt="Logo" 
                      className="w-10 h-10 object-cover rounded-xl"
                    />
                  </div>
                  <div>
                    <h1 className="text-2xl font-black drop-shadow-lg">Battle in Progress</h1>
                    <p className="text-white/80 text-sm font-semibold">{gameWordLength} Letter Words • Room: {roomCode}</p>
                  </div>
                </div>
                
                <div className="text-right">
                  <div className="flex items-center gap-4 text-white">
                    <div className="bg-white/20 rounded-xl px-3 py-2 flex items-center gap-2">
                      <Clock className="h-5 w-5" />
                      <span className="font-black text-lg">{formatTime(timeRemaining)}</span>
                    </div>
                    <div className="bg-white/20 rounded-xl px-3 py-2 flex items-center gap-2">
                      <div className="h-5 w-5 bg-white/60 rounded-full flex items-center justify-center">
                        <span className="text-orange-600 text-xs font-black">{lettersOnTable.length}</span>
                      </div>
                      <span className="font-semibold">Letters</span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Players */}
          <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
            <CardContent className="p-4">
              <h2 className="text-lg font-black text-gray-800 mb-3 flex items-center gap-2">
                <div className="w-3 h-3 bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full"></div>
                Battle Scores
              </h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {players.map((player, index) => (
                  <div key={index} className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-3 border-2 border-blue-200 shadow-sm">
                    <div className="font-black text-gray-800 text-sm">{player.name}</div>
                    <div className="text-2xl font-black text-blue-600">{player.score}</div>
                    <div className="text-xs text-gray-600 font-semibold">points</div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Letter Grid */}
          <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
            <CardContent>
              <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-12 gap-3 min-h-[280px] p-6">
                {lettersOnTable.map((letterObj) => (
                  <button
                    key={letterObj.id}
                    onClick={() => selectLetter(letterObj.id, letterObj.letter)}
                    className={`aspect-square rounded-2xl font-black text-2xl border-3 transition-all duration-200 transform hover:scale-110 flex items-center justify-center min-h-[70px] shadow-lg letter-tile ${
                      selectedLetters.find(l => l.id === letterObj.id)
                        ? 'bg-gradient-to-r from-orange-500 to-amber-500 text-white border-white scale-105 shadow-2xl rotate-3'
                        : 'bg-gradient-to-r from-blue-50 to-white border-blue-300 hover:border-orange-400 hover:bg-gradient-to-r hover:from-orange-50 hover:to-amber-50 text-gray-800'
                    }`}
                  >
                    {letterObj.letter}
                  </button>
                ))}
                {lettersOnTable.length === 0 && (
                  <div className="col-span-full flex items-center justify-center h-40 text-gray-500">
                    <div className="text-center">
                      <div className="text-4xl mb-2">⏳</div>
                      <div className="text-lg font-semibold">Preparing letters...</div>
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Word Formation */}
          <Card className="bg-gradient-to-r from-indigo-500 to-purple-600 shadow-2xl border-0 rounded-2xl game-container">
            <CardContent className="p-6">
              <div className="space-y-4">
                <h3 className="text-xl font-black text-white text-center drop-shadow-lg">Your Word</h3>
                
                {/* Current word display */}
                <div className="flex justify-center">
                  <div className="flex gap-3 min-h-[70px] items-center bg-white/10 rounded-2xl p-4 backdrop-blur-sm">
                    {selectedLetters.map((letter, index) => (
                      <div
                        key={`${letter.id}-${index}`}
                        className="w-14 h-14 bg-gradient-to-r from-white to-gray-100 border-3 border-orange-400 rounded-2xl flex items-center justify-center font-black text-2xl text-gray-800 letter-tile shadow-lg transform rotate-1"
                      >
                        {letter.letter}
                      </div>
                    ))}
                    {selectedLetters.length === 0 && (
                      <div className="text-white/80 text-lg font-semibold">Tap letters to build your word...</div>
                    )}
                  </div>
                </div>

                {/* Submit and Clear buttons */}
                <div className="flex gap-4 justify-center">
                  <button 
                    onClick={submitWord} 
                    disabled={selectedLetters.length !== gameWordLength}
                    className={`px-8 py-4 rounded-2xl font-black text-lg shadow-xl transition-all duration-200 transform ${
                      selectedLetters.length === gameWordLength
                        ? 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:scale-105 hover:shadow-2xl'
                        : 'bg-gray-400 text-gray-600 cursor-not-allowed'
                    }`}
                  >
                    ⚔️ SUBMIT
                  </button>
                  <button 
                    onClick={clearSelection}
                    disabled={selectedLetters.length === 0}
                    className={`px-8 py-4 rounded-2xl font-black text-lg shadow-xl transition-all duration-200 transform ${
                      selectedLetters.length > 0
                        ? 'bg-gradient-to-r from-red-500 to-pink-500 text-white hover:scale-105 hover:shadow-2xl'
                        : 'bg-gray-400 text-gray-600 cursor-not-allowed'
                    }`}
                  >
                    🗑️ CLEAR
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Messages and Rules */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Messages */}
            {messages.length > 0 && (
              <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
                <CardHeader>
                  <CardTitle className="text-lg">Game Feed</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-40 overflow-y-auto">
                    {messages.slice(-5).map((msg, index) => (
                      <p key={index} className="text-sm p-2 bg-gray-50 rounded">
                        {msg.text}
                      </p>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Rules Section for Playing */}
            <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
              <CardHeader>
                <CardTitle className="text-lg flex items-center justify-between">
                  Letter Points
                  <Button
                    variant="ghost"
                    onClick={() => setShowRules(!showRules)}
                    className="text-sm px-2 py-1"
                  >
                    {showRules ? '▼' : '▶'}
                  </Button>
                </CardTitle>
              </CardHeader>
              {showRules && (
                <CardContent>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(letterScores).map(([points, letters]) => (
                      <div key={points} className="flex items-center justify-between">
                        <span className="font-medium text-gray-700">{points}pt:</span>
                        <span className="font-mono text-gray-600 text-right">{letters.join(' ')}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              )}
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (gameState === 'profile') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-400 via-indigo-500 to-purple-600 relative overflow-hidden p-4">
        {/* Animated background elements */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-10 left-10 w-32 h-32 bg-orange-300 rounded-full blur-xl animate-pulse"></div>
          <div className="absolute bottom-20 right-20 w-28 h-28 bg-yellow-300 rounded-full blur-lg animate-bounce delay-1000"></div>
        </div>

        <div className="relative z-10 max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <Card className="bg-gradient-to-r from-orange-500 to-amber-500 shadow-2xl border-0 rounded-2xl overflow-hidden game-container">
            <CardContent className="p-6">
              <div className="flex justify-between items-center text-white">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 bg-white rounded-2xl flex items-center justify-center shadow-lg overflow-hidden">
                    {currentUser?.picture ? (
                      <img 
                        src={currentUser.picture} 
                        alt="Profile" 
                        className="w-14 h-14 object-cover rounded-xl"
                      />
                    ) : (
                      <img 
                        src="https://customer-assets.emergentagent.com/job_wordplay-hub-2/artifacts/4qngir0x_nikki%20logo.png" 
                        alt="Default" 
                        className="w-14 h-14 object-cover rounded-xl"
                      />
                    )}
                  </div>
                  <div>
                    <h1 className="text-3xl font-black drop-shadow-lg">{currentUser?.name || 'Warrior'}</h1>
                    <p className="text-white/80 text-sm font-semibold">ELO Rating: {currentUser?.elo_rating || 1000}</p>
                  </div>
                </div>
                
                <div className="flex gap-3">
                  <button 
                    onClick={() => setGameState('menu')}
                    className="bg-white/20 hover:bg-white/30 px-4 py-2 rounded-xl font-black text-white transition-all"
                  >
                    🎮 Play Game
                  </button>
                  <button 
                    onClick={handleLogout}
                    className="bg-red-500/80 hover:bg-red-600 px-4 py-2 rounded-xl font-black text-white transition-all"
                  >
                    🚪 Logout
                  </button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-black text-blue-600">{currentUser?.total_games || 0}</div>
                <div className="text-sm font-bold text-gray-600">Total Battles</div>
              </CardContent>
            </Card>
            
            <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-black text-green-600">{currentUser?.total_wins || 0}</div>
                <div className="text-sm font-bold text-gray-600">Victories</div>
              </CardContent>
            </Card>
            
            <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-black text-orange-600">{currentUser?.total_score || 0}</div>
                <div className="text-sm font-bold text-gray-600">Total Points</div>
              </CardContent>
            </Card>
            
            <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
              <CardContent className="p-4 text-center">
                <div className="text-3xl font-black text-purple-600">
                  {currentUser?.total_games ? Math.round((currentUser.total_wins / currentUser.total_games) * 100) : 0}%
                </div>
                <div className="text-sm font-bold text-gray-600">Win Rate</div>
              </CardContent>
            </Card>
          </div>

          {/* Global Leaderboard Preview */}
          <Card className="bg-white/95 backdrop-blur-lg shadow-xl border-0 rounded-2xl game-container">
            <CardContent className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-2xl font-black text-gray-800">🏆 Global Leaderboard</h2>
                <span className="text-sm bg-gradient-to-r from-orange-500 to-amber-500 text-white px-3 py-1 rounded-full font-bold">
                  TOP WARRIORS
                </span>
              </div>
              
              <div className="space-y-3">
                <div className="text-center py-8 text-gray-500">
                  <div className="text-4xl mb-2">⏳</div>
                  <div className="font-semibold">Connect to internet to see global rankings</div>
                  <div className="text-sm text-gray-400 mt-2">
                    Battle against other players to earn ELO and climb the ranks!
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Back to Game */}
          <div className="text-center">
            <button 
              onClick={() => setGameState('menu')}
              className="bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 hover:from-green-600 hover:via-emerald-600 hover:to-teal-600 text-white font-black py-4 px-8 text-lg rounded-2xl shadow-xl transform hover:scale-105 transition-all duration-200"
            >
              ⚔️ Ready for Battle
            </button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default App;