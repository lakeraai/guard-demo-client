import React, { useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';

interface KeyInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
}

const KeyInput: React.FC<KeyInputProps> = ({
  label,
  value,
  onChange,
  placeholder = "Enter your API key",
  required = false,
}) => {
  const [showKey, setShowKey] = useState(false);

  const toggleVisibility = () => {
    setShowKey(!showKey);
  };

  const maskKey = (key: string) => {
    if (!key) return '';
    if (key.length <= 8) return '*'.repeat(key.length);
    return key.substring(0, 4) + '*'.repeat(key.length - 8) + key.substring(key.length - 4);
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">
        {label}
        {required && <span className="text-red-500 ml-1">*</span>}
      </label>
      <div className="relative">
        <input
          type="password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={value ? (showKey ? value : maskKey(value)) : placeholder}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent pr-10"
        />
        {value && (
          <button
            type="button"
            onClick={toggleVisibility}
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 hover:text-gray-600"
          >
            {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {value && (
        <p className="text-xs text-gray-500">
          {showKey ? 'Click the eye icon to hide the key' : 'Click the eye icon to reveal the full key'}
        </p>
      )}
    </div>
  );
};

export default KeyInput;

