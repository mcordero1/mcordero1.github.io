// BUSCADOR DE CONTENIDO

// Ejecutando funciones: en este caso, al hacer click en la lupita me va a tirar para abajo el input del buscador
document.getElementById("icon-search").addEventListener("click", mostrar_buscador);


// Declarando variables: relación de id del HTML con el JS. Con esto vamos a poder tener el cód más ordenado.
bars_search =       document.getElementById("ctn-bars-search");
cover_ctn_search =  document.getElementById("cover-ctn-search");
inputSearch =       document.getElementById("inputSearch"); // Para ir guardando las variables en el input search!
box_search =        document.getElementById("box-search"); // Esto es para la barra del desplegable

// Función para mostrar el buscador
function mostrar_buscador() {
    bars_search.style.top= "80px";
}

// Filtro de búsqueda del search-bar
function buscador_interno() {
    filter = inputSearch.value.toUpperCase(); // variable filter: de esta manera, lo que ponga en minúscula en el input me lo reconoce el buscador como  si fuesen mayúsculas también.
}