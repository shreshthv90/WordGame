import React, { useState, useEffect, useCallback } from 'react';
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

function App() {
  const [gameState, setGameState] = useState('menu'); // 'menu', 'lobby', 'playing'
  const [roomCode, setRoomCode] = useState('');
  const [playerName, setPlayerName] = useState('');
  const [players, setPlayers] = useState([]);
  const [lettersOnTable, setLettersOnTable] = useState([]);
  const [selectedLetters, setSelectedLetters] = useState([]);
  const [currentWord, setCurrentWord] = useState('');
  const [messages, setMessages] = useState([]);
  const [gameStarted, setGameStarted] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  
  const addMessage = (text) => {
    setMessages(prev => [...prev, { text, timestamp: Date.now() }].slice(-10));
  };

  const createRoom = async () => {
    try {
      const response = await axios.post(`${API}/create-room`);
      const data = response.data;
      setRoomCode(data.room_code);
      setGameState('lobby');
      setConnectionStatus('connected');
      
      setPlayers([{ name: playerName, score: 0 }]);
      addMessage('Room created successfully!');
    } catch (error) {
      console.error('Error creating room:', error);
      addMessage('Failed to create room');
    }
  };

  const joinRoom = () => {
    if (roomCode && playerName) {
      setGameState('lobby');
      setConnectionStatus('connected');
      setPlayers([{ name: playerName, score: 0 }]);
      addMessage('Joined room successfully!');
    }
  };

  const startGame = () => {
    setGameStarted(true);
    setGameState('playing');
    addMessage('Game started! Letters will appear every 4 seconds.');
    
    // Start adding letters for demo
    addLettersToTable();
  };

  const addLettersToTable = () => {
    const letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'];
    const randomLetter = letters[Math.floor(Math.random() * letters.length)];
    const newLetter = {
      id: Date.now().toString(),
      letter: randomLetter,
      timestamp: Date.now()
    };
    
    setLettersOnTable(prev => [...prev, newLetter]);
  };

  // Add letters every 4 seconds when game is playing
  useEffect(() => {
    let interval;
    if (gameStarted && gameState === 'playing') {
      interval = setInterval(() => {
        addLettersToTable();
      }, 4000);
    }
    return () => clearInterval(interval);
  }, [gameStarted, gameState]);

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
    if (currentWord.length >= 3) {
      // Simple word validation (you can expand this)
      const score = currentWord.length * 2; // Simple scoring
      
      // Remove selected letters from table
      setLettersOnTable(prev => 
        prev.filter(l => !selectedLetters.some(sel => sel.id === l.id))
      );
      
      setSelectedLetters([]);
      setCurrentWord('');
      addMessage(`You scored ${score} points with "${currentWord.toUpperCase()}"!`);
      
      // Update players
      setPlayers(prev => 
        prev.map(p => p.name === playerName ? { ...p, score: p.score + score } : p)
      );
    }
  };

  const clearSelection = () => {
    setSelectedLetters([]);
    setCurrentWord('');
  };

  if (gameState === 'menu') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-red-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-2xl border-0 bg-white/95 backdrop-blur-sm">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto w-16 h-16 bg-gradient-to-br from-amber-500 to-orange-600 rounded-2xl flex items-center justify-center mb-4">
              <Zap className="h-8 w-8 text-white" />
            </div>
            <CardTitle className="text-3xl font-bold bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent">
              WordSmith
            </CardTitle>
            <p className="text-gray-600 text-sm">Multiplayer Word Racing Game</p>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <Input
                placeholder="Enter your name"
                value={playerName}
                onChange={(e) => setPlayerName(e.target.value)}
                className="text-center text-lg font-medium border-2 border-gray-200 focus:border-amber-400"
              />
            </div>
            
            <div className="space-y-3">
              <Button 
                onClick={createRoom} 
                className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white font-semibold py-3 text-lg rounded-xl shadow-lg"
                disabled={!playerName}
              >
                Create New Game
              </Button>
              
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <Separator className="w-full" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-white px-2 text-gray-500">Or</span>
                </div>
              </div>
              
              <div className="space-y-2">
                <Input
                  placeholder="Enter room code"
                  value={roomCode}
                  onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                  className="text-center text-lg font-mono tracking-wider border-2 border-gray-200 focus:border-amber-400"
                />
                <Button 
                  onClick={joinRoom} 
                  variant="outline" 
                  className="w-full border-2 border-amber-500 text-amber-600 hover:bg-amber-50 font-semibold py-3 text-lg rounded-xl"
                  disabled={!playerName || !roomCode}
                >
                  Join Game
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (gameState === 'lobby') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-red-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-2xl shadow-2xl border-0 bg-white/95 backdrop-blur-sm">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-bold text-gray-800">
              Game Lobby
            </CardTitle>
            <div className="flex items-center justify-center gap-4">
              <div className="flex items-center gap-2 text-lg font-mono text-amber-600 bg-amber-50 py-2 px-4 rounded-lg">
                Room Code: <span className="font-bold text-xl">{roomCode}</span>
              </div>
              <div className="flex items-center gap-2">
                {connectionStatus === 'connected' ? 
                  <Wifi className="h-5 w-5 text-green-500" /> : 
                  <WifiOff className="h-5 w-5 text-red-500" />
                }
                <span className="text-sm text-gray-600 capitalize">{connectionStatus}</span>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-gray-700">
                <Users className="h-5 w-5" />
                <span className="font-semibold">Players ({players.length})</span>
              </div>
              <div className="grid gap-2">
                {players.map((player, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="font-medium">{player.name}</span>
                    <Badge variant="secondary">{player.score} pts</Badge>
                  </div>
                ))}
              </div>
            </div>
            
            {players.length > 0 && !gameStarted && (
              <Button 
                onClick={startGame}
                className="w-full bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white font-semibold py-3 text-lg rounded-xl"
              >
                Start Game
              </Button>
            )}
            
            {messages.length > 0 && (
              <div className="border-t pt-4">
                <h3 className="font-semibold text-gray-700 mb-2">Game Messages</h3>
                <div className="space-y-1 max-h-32 overflow-y-auto">
                  {messages.map((msg, index) => (
                    <p key={index} className="text-sm text-gray-600 p-2 bg-gray-50 rounded">
                      {msg.text}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  if (gameState === 'playing') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-amber-50 via-orange-50 to-red-50 p-4">
        <div className="max-w-6xl mx-auto space-y-6">
          {/* Header */}
          <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Trophy className="h-5 w-5 text-amber-500" />
                    <span className="font-semibold">Room: {roomCode}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5 text-blue-500" />
                    <span>Letters: {lettersOnTable.length}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {connectionStatus === 'connected' ? 
                      <Wifi className="h-4 w-4 text-green-500" /> : 
                      <WifiOff className="h-4 w-4 text-red-500" />
                    }
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  {players.map((player, index) => (
                    <div key={index} className="text-right">
                      <div className="font-semibold text-sm">{player.name}</div>
                      <div className="text-lg font-bold text-amber-600">{player.score}</div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Letter Table */}
          <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
            <CardHeader>
              <CardTitle className="text-center">Letter Table</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-8 sm:grid-cols-10 md:grid-cols-12 lg:grid-cols-14 gap-2 min-h-[200px] p-4">
                {lettersOnTable.map((letterObj) => (
                  <button
                    key={letterObj.id}
                    onClick={() => selectLetter(letterObj.id, letterObj.letter)}
                    className={`aspect-square rounded-lg font-bold text-lg border-2 transition-all duration-200 transform hover:scale-105 flex items-center justify-center ${
                      selectedLetters.find(l => l.id === letterObj.id)
                        ? 'bg-amber-500 text-white border-amber-600 scale-95'
                        : 'bg-white border-gray-300 hover:border-amber-400 hover:bg-amber-50'
                    }`}
                  >
                    {letterObj.letter}
                  </button>
                ))}
                {lettersOnTable.length === 0 && (
                  <div className="col-span-full flex items-center justify-center h-32 text-gray-500">
                    Waiting for letters to appear...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Word Formation */}
          <Card className="bg-white/95 backdrop-blur-sm shadow-lg border-0">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <div className="flex-1">
                  <div className="text-sm text-gray-600 mb-1">Current Word:</div>
                  <div className="text-2xl font-bold font-mono bg-gray-50 p-3 rounded-lg min-h-[3rem] flex items-center">
                    {currentWord || 'Select letters to form a word...'}
                  </div>
                </div>
                <div className="space-x-2">
                  <Button 
                    onClick={clearSelection}
                    variant="outline"
                    className="px-6"
                    disabled={selectedLetters.length === 0}
                  >
                    Clear
                  </Button>
                  <Button 
                    onClick={submitWord}
                    className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 px-6"
                    disabled={currentWord.length < 3}
                  >
                    Submit Word
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

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
        </div>
      </div>
    );
  }

  return null;
}

export default App;