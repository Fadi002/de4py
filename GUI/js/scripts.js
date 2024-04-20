/*************Dont touch*************/
var injected;
var path;
var bin_path;
var analyzer_handle;
/*************Dont touch*************/

setTimeout(showMenu, 2000);

eel.expose(dead_process);

function generateRandomString(length) {
    var result = '';
    var characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (var i = 0; i < length; i++) {
        result += characters.charAt(Math.floor(Math.random() * characters.length));
    }
    return result;
}

async function change_title() {
    document.title = generateRandomString(Math.floor(Math.random() * (30 - 10 + 1)) + 10);
}

function dead_process() {
    injected = false;
    analyzer_handle = false;
    MFBOX.checked = false
    MPBOX.checked = false
    MCBOX.checked = false
    MCDUMPBOX.checked = false
    SSLBOX.checked = false
    PYCDUMB.checked = false
    navto("pyshell")
    createnotification("warning", "Process crashed/died/killed");
}

eel.expose(add_text_winapihook);
function add_text_winapihook(text) {
    var outputwinAPIhooks = document.getElementById('outputwinapihooks')
    outputwinAPIhooks.textContent = outputwinAPIhooks.textContent+"\n"+text;
}

async function exec_command(command) {
    if (command == 'ShowConsole') {
        var pid = document.getElementById('scpid')
        if (pid.value.trim() == '') {
            createnotification('warning', "Type process id first");
            return;
        }
        pid_widget(0)
        document.getElementById('outputPYSHELL').textContent = await eel.showconsole(pid.value.trim())();
        createnotification("success", "Command executed");
        return;
    }
    if (!injected) {
        createnotification("failure", "Please injected a process first")
    } else {
        if (command == 'DumpStrings') {
            document.getElementById('outputPYSHELL').textContent = await eel.dumpstring()();
            createnotification("success", "Command executed");
        } else if (command == 'GetFunctions') {
            document.getElementById('outputPYSHELL').textContent = await eel.getfunctions()();
            createnotification("success", "Command executed");
        } else if (command == 'DeattachDLL') {
            injected = false;
            analyzer_handle = false;
            MFBOX.checked = false
            MPBOX.checked = false
            MCBOX.checked = false
            MCDUMPBOX.checked = false
            SSLBOX.checked = false
            PYCDUMB.checked = false
            if (eel.write_to_pipe(command)) {
                createnotification("success", "Command executed");
            }
        } else if (command == "ExecPY") {
            var path = await eel.file_explorer()();
            document.getElementById('outputPYSHELL').textContent = await eel.execpython(path)();
            createnotification("success", "Command executed");
        } else if (command == "GetAnalyzerHandle") {
            if (!analyzer_handle) {
                document.getElementById('outputPYSHELL').textContent = await eel.openanalyzerhandle()();
                analyzer_handle = true;
                createnotification("success", "Command executed");
            } else {
                navto('winAPIhooking');
            }
        } else {
            if (eel.write_to_pipe(command)) {
                createnotification("success", "Command executed");
            }
        }
    }
}

async function loadPlugins() {
    eel.load_plugins();
    let pluginsContainer = document.getElementById('plugins-container');
    let pluginsHtml = await eel.get_plugins()();
    if (!pluginsHtml) {
        document.getElementById('plugins').innerHTML = "<h1>No plugins where loaded</h1>";
    }
    pluginsContainer.innerHTML = pluginsHtml;
}


function pid_widget(method) {
    if (!method) {
        document.getElementById('IDKWHATSHOULDINAMEIT').style.display = 'none';
    } else {
        document.getElementById('IDKWHATSHOULDINAMEIT').style.display = 'flex';
    }
}

function updatetime() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    const seconds = now.getSeconds().toString().padStart(2, '0');
    document.getElementById('clock').textContent = `${hours}:${minutes}:${seconds}`;
}

function navto(id) {
    var sec = document.getElementsByTagName('section');
    for (var i = 0; i < sec.length; i++) {
        sec[i].classList.add('hidden');
        sec[i].classList.remove('active');
    }
    var as = document.getElementById(id);
    as.classList.remove('hidden');
    as.classList.add('active');
}

async function loadchangelog() {
    try {
        var response = await eel.changelog()();
        var data = JSON.parse(response);
        changelogd(data);
    } catch (err) {
        console.log('Error loading changelog:', err);
    }
}

function showMenu() {
    var loadingScreen = document.getElementsByClassName('loading-screen')[0];
    loadingScreen.style.display = 'none';
}

function changelogd(data) {
    const logContainer = document.getElementById('changeLog');
    data.forEach(versionData => {
        const versionElement = document.createElement('div');
        versionElement.classList.add('version');
        versionElement.innerHTML = `<h3>Version ${versionData.version}</h3>`;
        const changesList = document.createElement('ul');
        versionData.changes.forEach(change => {
            const changeItem = document.createElement('li');
            changeItem.textContent = change;
            changesList.appendChild(changeItem);
        });
        versionElement.appendChild(changesList);
        logContainer.appendChild(versionElement);
    });
}

async function load_info() {
    eel.get_info()().then(data => {
        document.getElementById('pv').textContent = data['pv'];
        document.getElementById('arch').textContent = data['arch'];
        document.getElementById('os').textContent = data['os'];
    });
}

function createnotification(type, message) {
    const container = document.getElementById('notification-container');

    if (container.childElementCount >= 1) {
        const firstnotification = container.firstElementChild;
        if (firstnotification) {
            container.removeChild(firstnotification);
        }
    }
    var notification = document.createElement('div');
    var content = document.createElement('div');
    var progress = document.createElement('div');
    var icon = document.createElement('div');
    notification.className = 'notification-bar ' + type;
    content.className = 'notification-content';
    content.innerHTML = message;
    progress.className = 'notification-progress';
    icon.className = 'notification-icon ' + type;
    notification.appendChild(icon);
    notification.appendChild(content);
    notification.appendChild(progress);
    container.appendChild(notification);
    setTimeout(function() {
        container.removeChild(notification);
    }, 5000);
}

async function injectpyshell(typeinject) {
    const loadingspin = document.getElementById('loading-spin');
    const loadingSpinner = document.getElementById('loading-spinner');
    const pidinput = document.getElementById("pidinput");
    const outputt = document.getElementById('outputPYSHELL');
    if (pidinput.value.trim() == '') {
        createnotification('warning', "Type process id first");
        return
    }
    loadingspin.style.display = 'block';
    loadingSpinner.style.display = 'block';
    if (typeinject == 'normal') {
        try {
            const result = await eel.inject_shell(pidinput.value.trim())();
            outputt.textContent = result;
            injected = true;
            createnotification('success', 'pyshell injector function executed');
        } catch {
            createnotification('failure', 'pyshell injector function failed');
            outputt.textContent = `failed to inject pyshell`;
        }
    } else {
        try {
            const result = await eel.stealth_inject_shell(pidinput.value.trim())();
            outputt.textContent = result;
            injected = true;
            createnotification('success', 'pyshell injector function executed');
        } catch {
            createnotification('failure', 'pyshell injector function failed');
            outputt.textContent = `failed to inject pyshell`;
        }
    }  
    loadingspin.style.display = 'none';
    loadingSpinner.style.display = 'none';
}

async function startdeobf() {
    const loadingspin = document.getElementById('loading-spin');
    const loadingSpinner = document.getElementById('loading-spinner');
    const outputt = document.getElementById('outputDEOBF');
    if (!path) {
        createnotification('warning', "Select a file first");
        return
    }
    loadingspin.style.display = 'block';
    loadingSpinner.style.display = 'block';
    try {
        const result = await eel.protector_detector(path)();
        outputt.textContent = result;
        createnotification('success', 'Deobfuscation function executed');
    } catch (error) {
        createnotification('failure', 'Deobfuscation function failed');
        outputt.textContent = `An error occurred: ${error}`;
    }
    loadingspin.style.display = 'none';
    loadingSpinner.style.display = 'none';
}

async function getpath(x) {
    var dosya_path = await eel.file_explorer()();
    if (dosya_path) {
        var filename = dosya_path.match(/\/([^\/]+)$/);
        if (filename && filename.length > 1) {
            if (x) {
                document.getElementById('selectedFileName1').textContent = filename[1];
                bin_path = dosya_path
            } else {
                document.getElementById('selectedFileName').textContent = filename[1];
                path = dosya_path
            }   
        }
    }
}

async function analyzer_command(command) {
    if (!bin_path) {
        createnotification('warning', "Select a file first");
        return
    }
    if (command == "detect_packer") {
        if (bin_path.endsWith(".exe")) {
            document.getElementById('outputanalyzer').textContent = await eel.detect_packer(bin_path)();
            createnotification("success", "Command executed");
            return
        } else {
            createnotification("failure", "only exe files are supported")
            return
        }
    } else if (command == "unpack_exe") {
        if (bin_path.endsWith(".exe")) {
            document.getElementById('outputanalyzer').textContent = await eel.unpack_file(bin_path)();
            createnotification("success", "Command executed");
            return
        } else {
            createnotification("failure", "only exe files are supported")
            return
        }
    } else if (command == "sus_strings_lookup") {
        document.getElementById('outputanalyzer').textContent = JSON.stringify(JSON.parse(await eel.sus_strings_lookup(bin_path)()), null, 2);
        createnotification("success", "Command executed");
        return
    } else if (command == "all_strings_lookup") {
        document.getElementById('outputanalyzer').textContent = await eel.all_strings_lookup(bin_path)();
        createnotification("success", "Command executed");
        return
    } else if (command == "get_file_hashs") {
        document.getElementById('outputanalyzer').textContent = await eel.get_file_hashs(bin_path)();
        createnotification("success", "Command executed");
        return
    }
}
eel.expose(applyCSS);
function applyCSS(cssCode) {
    const styleElement = document.createElement("style");
    styleElement.type = "text/css";
    if (styleElement.styleSheet) {
        styleElement.styleSheet.cssText = cssCode;
    } else {
        styleElement.appendChild(document.createTextNode(cssCode));
    }
    document.head.appendChild(styleElement);
    const bodyElement = document.getElementsByTagName('body')[0];
    bodyElement.style.cssText += cssCode;
}

function updateConfig(key, value) {
    eel.update_config(key, value)();
    updateCheckboxes();
}

eel.expose(updateCheckboxes);

async function updateCheckboxes(config) {
    var config = await eel.get_config()() 
    document.getElementById('RPC').checked = config.__RPC__;
    document.getElementById('STEALTH_TITLE').checked = config.__STEALTH_TITLE__;
    document.getElementById('REPORT_ERRORS').checked = config.__REPORT_ERRORS__;
    document.getElementById('LOAD_PLUGINS').checked = config.__LOAD_PLUGINS__;
}


document.addEventListener('DOMContentLoaded', async function() {
    loadchangelog();
    load_info();
    loadPlugins();
    updateCheckboxes();
    if (await eel.STEALTH_TITLE()()) {
        change_title()
    }
    document.getElementById("buildNumber").innerText = (await eel.get_config()()).__BUILD_NUM__;
    setInterval(updatetime, 1000);
    const navbar = document.getElementById('navbar');
    const menuToggle = document.getElementById('menulol');
    const buttons = document.querySelectorAll('.btn');
    const contentContainer = document.querySelector('.content-container');
    const MFBOX = document.getElementById('MFBOX');
    const MPBOX = document.getElementById('MPBOX');
    const MCBOX = document.getElementById('MCBOX');
    const MCDUMPBOX = document.getElementById('MCDUMPBOX');
    const SSLBOX = document.getElementById('SSLBOX');
    const PYCDUMB = document.getElementById('PYCDUMB');
    MCDUMPBOX.disabled = true;
    menuToggle.addEventListener('click', function() {
        navbar.style.left = (navbar.style.left === '0px' || navbar.style.left === '') ? '-310px' : '0px';
        menuToggle.style.left = (navbar.style.left === '0px') ? '220px' : '20px';
        contentContainer.classList.toggle('open');
    });
    MFBOX.addEventListener('change', async function() {
        if (this.checked) {
            add_text_winapihook(await eel.monitorfileshook(true)());
        } else {
            add_text_winapihook(await eel.monitorfileshook(false)());
        }
    });    
    MPBOX.addEventListener('change', async function() {
        if (this.checked) {
            add_text_winapihook(await eel.monitorprocesseshook(true)());
        } else {
            add_text_winapihook(await eel.monitorprocesseshook(false)());
        }
    });
    MCBOX.addEventListener('change', async function() {
        if (this.checked) {
            MCDUMPBOX.disabled = false;
            add_text_winapihook(await eel.monitorconnectionshook(true)());
        } else {
            add_text_winapihook(await eel.monitorconnectionshook(false)());
            MCDUMPBOX.disabled = true;
        }
    });
    MCDUMPBOX.addEventListener('change', async function() {
        if (this.checked) {
            add_text_winapihook(await eel.dumpsocketcontent(true)());
        } else {
            add_text_winapihook(await eel.dumpsocketcontent(false)());
        }
    });
    SSLBOX.addEventListener('change', async function() {
        if (this.checked) {
            add_text_winapihook(await eel.dumpopensslcontent(true)());
        } else {
            add_text_winapihook(await eel.dumpopensslcontent(false)());
        }
    });
    PYCDUMB.addEventListener('change', async function() {
        if (this.checked) {
            add_text_winapihook(await eel.pycdumper(true)());
        } else {
            add_text_winapihook(await eel.pycdumper(false)());
        }
    });
    buttons.forEach(function(button) {
        button.addEventListener('click', function() {
            buttons.forEach(function(btn) {
                btn.classList.remove('sebtn');
            });
            this.classList.add('sebtn');
        });
    });
    var progressBar = document.querySelector('.loading-bar-fill');
    var width = 0;
    var interval = setInterval(function() {
        if (width >= 100) {
            clearInterval(interval);
        } else {
            width++;
            progressBar.style.width = width + '%';
        }
    }, 20);
});