import React, { memo } from "react";
import { ipcRenderer } from "electron";

const TitleBar: React.FC = () => {
  const handleMinimize = () => {
    ipcRenderer.send("window:minimize");
  };

  const handleMaximize = () => {
    ipcRenderer.send("window:maximize");
  };

  const handleClose = () => {
    ipcRenderer.send("window:close");
  };

  return (
    <div
      className="flex items-center justify-between h-8 bg-gray-800 text-white draggable"
      onDoubleClick={handleMaximize}
    >
      <div className="ml-2">DASH</div>
      <div className="flex items-center">
        <button onClick={handleMinimize} className="px-4 py-1 hover:bg-gray-700 non-draggable">
          -
        </button>
        <button onClick={handleMaximize} className="px-4 py-1 hover:bg-gray-700 non-draggable">
          +
        </button>
        <button onClick={handleClose} className="px-4 py-1 hover:bg-red-500 non-draggable">
          x
        </button>
      </div>
    </div>
  );
};

export default memo(TitleBar);