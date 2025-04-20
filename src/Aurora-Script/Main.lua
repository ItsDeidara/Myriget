-- Aurora Script
scriptTitle = "Myriget"
scriptAuthor = "StonedModder"
scriptVersion = "1.0"
scriptDescription = "Downloads and extracts game files directly on your Xbox 360."
scriptIcon = "icon.png"
scriptPermissions = { "filesystem", "network" }

-- Define used enums
FilebrowserFlag = enum {
    ShowFiles           = 0x01,
    BaseDirAsRoot      = 0x02,
    HideCreateDir      = 0x04,
    DisableHomeDrives  = 0x08,
    DeviceSelect       = 0x10,
    SelectDirectory    = 0x20
}

-- Script settings
local SETTINGS = {
    PASTEBIN_URL = "",  -- Will be populated from pb.txt
    LOCAL_LINKS = true, -- Whether to use local links.json
    DELETE_AFTER_EXTRACT = true,
    DOWNLOAD_DIR = "",  -- Default download directory
    LAST_SELECTED = ""  -- Remember last selected game
}

-- Load Pastebin URL from pb.txt
function LoadPastebinURL()
    local pbPath = Script.GetScriptPath() .. "\\pb.txt"
    if FileSystem.FileExists(pbPath) then
        local file = io.open(pbPath, "r")
        if file then
            SETTINGS.PASTEBIN_URL = file:read("*all"):gsub("%s+$", "") -- Read and trim whitespace
            file:close()
        end
    end
end

-- Load settings from INI file
function LoadSettings()
    local settingsPath = Script.GetScriptPath() .. "\\settings.ini"
    if not FileSystem.FileExists(settingsPath) then
        -- Create default settings file
        local file = io.open(settingsPath, "w")
        if file then
            file:write("[Settings]\n")
            file:write("use_local_links=true\n")
            file:write("delete_after_extract=true\n")
            file:write("download_dir=\n")
            file:write("last_selected=\n")
            file:close()
        end
    end
    
    -- Load settings
    local file = io.open(settingsPath, "r")
    if file then
        for line in file:lines() do
            local key, value = string.match(line, "(%w+)%s*=%s*(.+)")
            if key == "use_local_links" then
                SETTINGS.LOCAL_LINKS = (value:lower() == "true")
            elseif key == "delete_after_extract" then
                SETTINGS.DELETE_AFTER_EXTRACT = (value:lower() == "true")
            elseif key == "download_dir" then
                SETTINGS.DOWNLOAD_DIR = value
            elseif key == "last_selected" then
                SETTINGS.LAST_SELECTED = value
            end
        end
        file:close()
    end
end

-- Load links.json from a specified path
function LoadLinks(path)
    local file = io.open(path, "r")
    if not file then
        return nil, "Could not open links.json"
    end
    
    local content = file:read("*all")
    file:close()
    
    local success, links = pcall(json.decode, content)
    if not success then
        return nil, "Invalid JSON format"
    end
    
    return links
end

-- Download links.json from pastebin
function DownloadLinks()
    if SETTINGS.PASTEBIN_URL == "" then
        return nil, "Pastebin URL not configured"
    end
    
    -- Download the file
    local http = require("socket.http")
    local response, err = http.request(SETTINGS.PASTEBIN_URL)
    if not response then
        return nil, "Failed to download links.json: " .. (err or "unknown error")
    end
    
    -- Parse JSON
    local success, links = pcall(json.decode, response)
    if not success then
        return nil, "Invalid JSON format from pastebin"
    end
    
    -- Save to local file for backup
    local file = io.open(Script.GetScriptPath() .. "\\links.json", "w")
    if file then
        file:write(response)
        file:close()
    end
    
    return links
end

-- Download a file with progress updates
function DownloadFile(url, destination, progressCallback)
    local http = require("socket.http")
    local ltn12 = require("ltn12")
    
    -- Create destination directory if it doesn't exist
    local dir = string.match(destination, "(.*\\)")
    if dir then
        FileSystem.CreateDirectory(dir)
    end
    
    -- Open destination file
    local file = io.open(destination, "wb")
    if not file then
        return false, "Could not create destination file"
    end
    
    -- Setup progress tracking
    local size = 0
    local downloaded = 0
    
    -- Get file size first
    local response = http.request{
        method = "HEAD",
        url = url,
        headers = {
            ["User-Agent"] = "Xbox/Aurora"
        }
    }
    if response and response.headers then
        size = tonumber(response.headers["content-length"]) or 0
    end
    
    -- Download the file
    local result, err = http.request{
        url = url,
        sink = ltn12.sink.chain(
            ltn12.sink.file(file),
            function(chunk)
                if chunk then
                    downloaded = downloaded + #chunk
                    if progressCallback then
                        progressCallback(size, downloaded)
                    end
                end
                return chunk
            end
        ),
        headers = {
            ["User-Agent"] = "Xbox/Aurora"
        }
    }
    
    file:close()
    
    if not result then
        os.remove(destination)
        return false, err
    end
    
    return true
end

-- Extract a zip file
function ExtractZip(zipPath, destination)
    local zip = require("zip")
    
    -- Create destination directory
    FileSystem.CreateDirectory(destination)
    
    -- Open zip file
    local zf, err = zip.open(zipPath)
    if not zf then
        return false, "Could not open zip file: " .. (err or "unknown error")
    end
    
    -- Extract each file
    for file in zf:files() do
        local success, err = zf:extract(file.filename, destination)
        if not success then
            zf:close()
            return false, "Failed to extract " .. file.filename .. ": " .. (err or "unknown error")
        end
    end
    
    zf:close()
    return true
end

function ShowSettings()
    -- Create settings menu
    local menu = require("Menu")
    menu.SetTitle("Download Manager Settings")
    
    -- Add menu items
    menu.AddMainMenuItem(menu.CreateMenuItem("Set Download Directory", function()
        local ret = Script.ShowFilebrowser("\\", "", FilebrowserFlag.SelectDirectory)
        if not ret.Canceled then
            SETTINGS.DOWNLOAD_DIR = ret.File.MountPoint .. "\\" .. ret.File.RelativePath .. ret.File.Name .. "\\"
            SaveSettings()
            Script.ShowNotification("Download directory updated!")
        end
    end))
    
    menu.AddMainMenuItem(menu.CreateMenuItem("Toggle Local/Remote Links", function()
        SETTINGS.LOCAL_LINKS = not SETTINGS.LOCAL_LINKS
        SaveSettings()
        Script.ShowNotification("Now using " .. (SETTINGS.LOCAL_LINKS and "local" or "remote") .. " links.json")
    end))
    
    menu.AddMainMenuItem(menu.CreateMenuItem("Toggle Delete After Extract", function()
        SETTINGS.DELETE_AFTER_EXTRACT = not SETTINGS.DELETE_AFTER_EXTRACT
        SaveSettings()
        Script.ShowNotification("Delete after extract: " .. (SETTINGS.DELETE_AFTER_EXTRACT and "enabled" or "disabled"))
    end))
    
    -- Show menu
    menu.Show()
end

function SaveSettings()
    local file = io.open(Script.GetScriptPath() .. "\\settings.ini", "w")
    if file then
        file:write("[Settings]\n")
        file:write("use_local_links=" .. tostring(SETTINGS.LOCAL_LINKS) .. "\n")
        file:write("delete_after_extract=" .. tostring(SETTINGS.DELETE_AFTER_EXTRACT) .. "\n")
        file:write("download_dir=" .. SETTINGS.DOWNLOAD_DIR .. "\n")
        file:write("last_selected=" .. SETTINGS.LAST_SELECTED .. "\n")
        file:close()
    end
end

function ShowGameMenu(links)
    -- Create game selection menu
    local menu = require("Menu")
    menu.SetTitle("Select Game to Download")
    menu.SetEmptyText("No games available")
    menu.SetSortAlphaBetically(true)
    
    -- Add menu items for each game
    for _, link in ipairs(links) do
        -- Only show games that aren't downloaded yet
        if not link.downloaded then
            local name = link.name or "Unknown Game"
            local size = link.size_bytes and string.format("%.2f GB", link.size_bytes / (1024*1024*1024)) or "Unknown size"
            local displayName = string.format("%s (%s)", name, size)
            
            -- Create menu item
            local menuItem = menu.CreateMenuItem(displayName, function()
                SETTINGS.LAST_SELECTED = name
                SaveSettings()
                ProcessGame(link)
            end)
            
            -- Add to menu
            menu.AddMainMenuItem(menuItem)
        end
    end
    
    -- Show menu
    menu.Show()
end

function ProcessGame(link)
    -- Check if download directory is configured
    if SETTINGS.DOWNLOAD_DIR == "" then
        Script.ShowMessageBox("Error", "Please configure download directory in settings first.", "OK")
        ShowSettings()
        return
    end
    
    -- Create download directory if it doesn't exist
    FileSystem.CreateDirectory(SETTINGS.DOWNLOAD_DIR)
    
    -- Update status
    Script.SetStatus("Downloading " .. (link.name or "game"))
    
    -- Download file
    local zipPath = SETTINGS.DOWNLOAD_DIR .. (link.name or "game") .. ".zip"
    local success, err = DownloadFile(link.url, zipPath, function(total, current)
        if Script.IsCanceled() then return false end
        Script.SetProgress((current / total) * 100)
    end)
    
    if success then
        -- Extract if download successful
        Script.SetStatus("Extracting " .. (link.name or "game"))
        success, err = ExtractZip(zipPath, SETTINGS.DOWNLOAD_DIR .. (link.name or "game"))
        
        if success then
            -- Update link status
            link.downloaded = true
            link.extracted = true
            
            -- Delete zip if configured
            if SETTINGS.DELETE_AFTER_EXTRACT then
                os.remove(zipPath)
            end
            
            -- Save updated links.json locally
            local file = io.open(Script.GetScriptPath() .. "\\links.json", "w")
            if file then
                file:write(json.encode(links))
                file:close()
            end
            
            Script.ShowNotification("Download and extraction complete!")
        else
            Script.ShowMessageBox("Error", "Failed to extract " .. (link.name or "game") .. ": " .. err, "OK")
        end
    else
        Script.ShowMessageBox("Error", "Failed to download " .. (link.name or "game") .. ": " .. err, "OK")
    end
end

-- Main function (required by Aurora)
function main()
    -- Load settings first
    LoadSettings()
    LoadPastebinURL()
    
    -- Show settings menu if no pastebin URL configured and using remote
    if not SETTINGS.LOCAL_LINKS and SETTINGS.PASTEBIN_URL == "" then
        Script.ShowMessageBox("Configuration Required", "Please create pb.txt with Pastebin URL in script directory", "OK")
        return
    end
    
    -- Load links
    local links, err
    if SETTINGS.LOCAL_LINKS then
        -- Try to load from script directory first
        links, err = LoadLinks(Script.GetScriptPath() .. "\\links.json")
    else
        -- Download from pastebin
        Script.SetStatus("Downloading links.json...")
        links, err = DownloadLinks()
    end
    
    if not links then
        Script.ShowMessageBox("Error", "Failed to load links: " .. err, "OK")
        return
    end
    
    -- Show game selection menu
    ShowGameMenu(links)
end 