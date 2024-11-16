document.addEventListener('DOMContentLoaded', function() {
    var calendarEl = document.getElementById('calendar');

    function loadEvents() {
        fetch('Eventi_Virgilio.it_selenium.json')
        .then(response => {
            console.log('Response:', response); // Log the response object
            if (!response.ok) {
                throw new Error('Errore nel caricamento degli eventi: ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            console.log('Data received:', data); // Log the fetched data
            const calendarEvents = prepareEvents(data);
            console.log('Eventi preparati:', calendarEvents); // Log prepared events
            initializeCalendar(calendarEvents);
        })
        .catch(error => {
            console.error('Errore durante il caricamento degli eventi:', error);
            alert(`Si è verificato un errore durante il caricamento degli eventi: ${error.message}`);
        });
    }

    function initializeCalendar(events) {
        console.log('Eventi inizializzati:', events); // Log for initialized events
        if (!Array.isArray(events)) {
            console.error('Errore: events non è un array:', events);
            return; // Exit if events is not an array
        }

        var calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'dayGridMonth',
            events: events,
            eventContent: function(info) {
                let price = info.event.extendedProps.price;
                let time = info.event.extendedProps.time;
                return {
                    html: `<b>${info.event.title}</b><br>${time} - ${price}`
                };
            },
            eventClick: function(info) {
                alert(`Descrizione: ${info.event.extendedProps.description}\nLuogo: ${info.event.extendedProps.location}\nIndirizzo: ${info.event.extendedProps.address}`);
            }
        });

        calendar.render();

        document.getElementById('nameFilter').addEventListener('input', function() {
            filterEventsByName(calendar, events);
        });
    }

    loadEvents();

    document.getElementById("updateEvents").addEventListener("click", async function() {
        const loadingBar = document.querySelector('.loading-bar');
    
        // Reset loading bar and make it visible
        loadingBar.style.width = '0%';
        loadingBar.parentElement.style.display = 'inline-block'; // Show the loading bar container
    
        // Start loading animation
        setTimeout(() => {
            loadingBar.style.width = '100%'; // Fill the loading bar
        }, 100); // A short delay to see the initial state
    
        try {
            const response = await fetch("http://127.0.0.1:5000/update-events", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const events = await response.json();
            displayEvents(events);  // Update the calendar with new events
        } catch (error) {
            console.error("Error updating events:", error);
        }
    
        // Reset loading bar after 10 seconds
        setTimeout(() => {
            loadingBar.style.width = '0%'; // Reset the loading bar after finishing
            loadingBar.parentElement.style.display = 'none'; // Hide the loading bar container
        }, 10000); // Keep it visible for 10 seconds
    });       
});

function prepareEvents(data) {
    // Assuming data is expected to be an array
    if (!Array.isArray(data)) {
        console.error('Errore: data non è un array:', data);
        return []; // Return an empty array if the format is incorrect
    }

    const events = data.flatMap(event => {
        const dateRangeEvents = parseDateRange(event['Data']);
        if (dateRangeEvents.length > 0) {
            return dateRangeEvents.map(date => createEvent(event, date));
        } else {
            return [createEvent(event, formatDateToISO(event['Data']))];
        }
    });
    console.log('Eventi preparati in prepareEvents:', events); // Log for prepared events
    return events;
}

function createEvent(event, startDate) {
    return {
        title: event['Titolo evento'],
        start: startDate,
        description: event['Descrizione Groq'] || event['Descrizione di Virgilio.it'], // Use the Groq description if available
        location: event['Luogo'],
        address: event['Indirizzo'] || "", // Include the address if it exists
        extendedProps: {
            price: Array.isArray(event['Prezzo']) ? event['Prezzo'].join(', ') : (event['Prezzo'] || "Non disponibile"),
            time: event['Orario'] || "Orario non specificato"
        }
    };
}

function formatDateToISO(dateStr) {
    const parts = dateStr.split('/');
    return `2024-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
}

function parseDateRange(dateRange) {
    const regex = /Dal (\d{1,2})\/(\d{1,2}) al (\d{1,2})\/(\d{1,2})/;
    const match = dateRange.match(regex);
    if (match) {
        const startDay = parseInt(match[1]);
        const startMonth = parseInt(match[2]) - 1;
        const endDay = parseInt(match[3]);
        const endMonth = parseInt(match[4]) - 1;

        const startDate = new Date(new Date().getFullYear(), startMonth, startDay);
        const endDate = new Date(new Date().getFullYear(), endMonth, endDay);

        const dates = [];
        for (let dt = startDate; dt <= endDate; dt.setDate(dt.getDate() + 1)) {
            dates.push(formatDateToISO(dt.toLocaleDateString("it-IT")));
        }
        return dates;
    }
    return [];
}

function filterEventsByName(calendar, events) {
    const searchTerm = document.getElementById('nameFilter').value.toLowerCase();
    const filteredEvents = events.filter(event => {
        return event.title.toLowerCase().includes(searchTerm);
    });

    calendar.removeAllEvents();
    calendar.addEventSource(filteredEvents); // Use filtered events
}
