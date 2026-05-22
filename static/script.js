function toggleDarkMode() {

    document.body.classList.toggle("light-mode");

    if(document.body.classList.contains("light-mode")){
        localStorage.setItem("theme", "light");
    } else {
        localStorage.setItem("theme", "dark");
    }
}

window.onload = () => {

    const theme = localStorage.getItem("theme");

    if(theme === "light"){
        document.body.classList.add("light-mode");
    }
}