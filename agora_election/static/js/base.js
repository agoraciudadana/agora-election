    /*
    This file is part of agora-election.
    Copyright (C) 2014 Eduardo Robles Elvira <edulix AT agoravoting DOT com>

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

(function(){

    var AE = this.AE = {}; // AE  means "Agora Election"
    var app = this.app = {};
    app.current_view = null;
    app.modal_dialog = null;

    var Checker = {};
    Checker.email = function(v) {
        var RFC822;
        RFC822 = /^([^\x00-\x20\x22\x28\x29\x2c\x2e\x3a-\x3c\x3e\x40\x5b-\x5d\x7f-\xff]+|\x22([^\x0d\x22\x5c\x80-\xff]|\x5c[\x00-\x7f])*\x22)(\x2e([^\x00-\x20\x22\x28\x29\x2c\x2e\x3a-\x3c\x3e\x40\x5b-\x5d\x7f-\xff]+|\x22([^\x0d\x22\x5c\x80-\xff]|\x5c[\x00-\x7f])*\x22))*\x40([^\x00-\x20\x22\x28\x29\x2c\x2e\x3a-\x3c\x3e\x40\x5b-\x5d\x7f-\xff]+|\x5b([^\x0d\x5b-\x5d\x80-\xff]|\x5c[\x00-\x7f])*\x5d)(\x2e([^\x00-\x20\x22\x28\x29\x2c\x2e\x3a-\x3c\x3e\x40\x5b-\x5d\x7f-\xff]+|\x5b([^\x0d\x5b-\x5d\x80-\xff]|\x5c[\x00-\x7f])*\x5d))*$/;
        return RFC822.test(v);
    };

    Checker.tlf = function (tlf) {
        if (!tlf) {
            return null;
        }
        tlf = tlf.trim();
        tlf = tlf.replace(/ /g, '');
        tlf = tlf.replace(/^0034/, "+34");
        tlf = tlf.replace(/^34/, "+34");
        if (!/^\+34/.test(tlf)) {
            tlf = "+34" + tlf;
        }
        var regExp = new RegExp(app_data.tlf_no_rx);
        if (!regExp.test(tlf)) {
            return null;
        }
        return tlf;
    };

    Checker.dni = function(v) {
        var regex;
        regex = /^[0-9]{8}[A-Za-z]{1}$/;

        if(!regex.test(v)) {
            return false;
        }

        var dni = parseInt(v);

        var mod_letters = 'TRWAGMYFPDXBNJZSQVHLCKE';
        var digits = v.substring(0, 8);
        var letter = v.substring(8, 9).toUpperCase();

        var expected = mod_letters.charAt(dni % 23);

        return letter == expected;
    };

    /**
     *  Main function, creates the router and starts the routing processing
     */
    var main = function() {
        app.modal_view = new AE.ModalDialogView();

        // process app_data
        var rx = /^(https?:\/\/[^/]+)\/[^/]+\/[^/]+\/election\//
        app_data.election.base_url = rx.exec(app_data.election.url)[1];

        // Initiate the router
        app.router = new AE.Router();

        // Start Backbone history a necessary step for bookmarkable URL's
        Backbone.history.start();
    };

    /**
     * Url router, launches the appropiate views depending on the current
     * #hashbang
     */
    AE.Router = Backbone.Router.extend({
        routes: {
            "": "home",
            "identify": "identify",
            "verify-sms": "verify_sms",
            "faq": "faq",
            "authorities": "authorities",
            "contact": "contact",
            'mail-sent': 'mail_sent',
            'verify-vote': 'security_center',
            'verify-tally': 'security_center',

        },

        removeCurrentView: function() {
            if(app.current_view) {
                app.current_view.remove();
                $("#renderall-wrapper").html('<div id="renderall"></div>');
            }
        },

        home: function() {
            this.removeCurrentView();
            app.current_view = new AE.HomeView();
        },

        identify: function() {
            this.removeCurrentView();
            app.current_view = new AE.IdentifyView();
        },

        verify_sms: function() {
            this.removeCurrentView();
            app.current_view = new AE.VerifySMSView();
        },

        faq: function() {
            this.removeCurrentView();
            app.current_view = new AE.FAQView();
        },

        authorities: function() {
            this.removeCurrentView();
            app.current_view = new AE.AuthoritiesView();
        },

        contact: function() {
            this.removeCurrentView();
            app.current_view = new AE.ContactView();
        },

        mail_sent: function() {
            this.removeCurrentView();
            app.current_view = new AE.MailSentView();
        },

        security_center: function() {
            this.removeCurrentView();
            if (!app.current_view ||
                app.current_view.class_name != "security-center")
            {
                app.current_view = new AE.SecurityCenterView();
            }
        }
    });

    /**
     * Home view - just renders the home page template with the app_data
     */
    AE.HomeView = Backbone.View.extend({
        el: "#renderall",

        events: {
            'click a.details': 'showDetails',
        },

        initialize: function() {
            this.template = _.template($("#template-home-view").html());
            this.tmplCandModalBody = _.template($("#template-candidate-modal-body").html());
            this.render();
        },

        render: function() {
            if (app_data.election.tally_released_at_date == null) {
                app_data.election.questions[0].answers = $.shuffle(app_data.election.questions[0].answers);
            }
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        },

        /**
         *  shows a modal dialog with the details of the candidate option
         */
        showDetails: function(e) {
            e.preventDefault();
            var candidate = $(e.target).data('candidate');
            var title = candidate.value;
            var body = this.tmplCandModalBody(candidate);
            app.modal_view.render(candidate.value, body, "");
        }
    });

    /**
     * Process the long description of a candidate getting only some short
     * description
     */
    AE.shortDetails = function(description)  {
        var ret = description.substr(0, 140);
        return ret.replace(/(<\/p>|<p>|<p|p>|<\/|>|<)/g, "") + " ..";
    };

    /**
     * Return the dict item with the given name from an url list of a candidate,
     * or null.
     */
    AE.findUrlByTitle = function(urls, title)  {
        for (var i = 0; i < urls.length; i++) {
            if (urls[i].title.indexOf(title) != -1) {
                return urls[i];
            }
        }
        return null;
    };

    /**
     * Return the candidate by name.
     */
    AE.findCandidateByName = function(name)  {
        for (var i = 0; i < app_data.election.questions[0].answers.length; i++) {
            var candidate = app_data.election.questions[0].answers;
            if (candidate.value == name) {
                return candidate;
            }
        }
        return null;
    }

    /**
     * Identify view - shows the form where the user enters identification
     * details, most importantly the telephone number.
     */
    AE.IdentifyView = Backbone.View.extend({
        el: "#renderall",

        events: {
            'click #identify-action': 'processForm'
        },

        initialize: function() {
            this.template = _.template($("#template-identify-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        },

        /**
         * Used in setError and processForm to detect errors
         */
        errorFlag: false,

        /**
         * detects when we are sending a petition
         */
        sendingFlag: false,

        /**
         *  Help function to set the
         */
        setError: function(selector, text) {
            this.errorFlag = true;
            $(selector).parent().find(".help-block").html(text);
            $(selector).closest(".form-group").addClass("has-error");
        },

        /**
         * Does the heavy duty stuff in this view, processes the form, showing
         * errors if any, or sending the data and showing the SMS code
         * verification form.
         */
        processForm: function(e) {
            if (this.sendingFlag) {
                return;
            }
            this.sendingFlag = true;
            // reset errors
            this.errorFlag = false;
            $("#identify-action").attr("disabled", "disabled");
            $(".form-group.has-error .help-block").each(function() {
                $(this).html("");
            });
            $(".form-group").removeClass("has-error");

            // get the data
            var first_name = $("#first-name").val().trim();
            var last_name = $("#last-name").val().trim();
            var email = $("#email").val().trim();
            var dni = $("#dni").val().trim();
            var tlf = $("#tlf").val().trim();
            var postal_code = parseInt($("#postal-code").val().trim());
            var above_age = $("#above-age:checked").length == 1;
            var mail_updates = $("#receive-mail-updates:checked").length == 1;
            var accept_conditions = $("#accept-conditions:checked").length == 1;

            // start checking
            if (first_name.length < 3 || first_name.length >= 60)
            {
                this.setError("#first-name", "Obligatorio, de 3 a 60 caracteres");
            }

            if (last_name.length < 3 || last_name.length >= 100)
            {
                this.setError("#last-name", "Obligatorio, de 3 a 60 caracteres");
            }

            if (email.length < 3 || email.length >= 140 ||
                    !Checker.email(email))
            {
                this.setError("#email", "Debes introducir una dirección email válida");
            }

            app_data.tlf = Checker.tlf(tlf)
            if (!app_data.tlf) {
                this.setError("#tlf", "Debes introducir un teléfono español válido. Ejemplo: 666 666 666");
            }

            if(!Checker.dni(dni)) {
                this.setError("#dni", "Debes introducir un DNI válido");
            }

            if (!/^[0-9]+$/.test(postal_code) || postal_code < 1 || postal_code > 100000)
            {
                this.setError("#postal-code", "Código postal inválido");
            }

            if (!above_age) {
                this.setError("#above-age", "Debes ser mayor de edad para votar");
            }

            if (!accept_conditions) {
                this.setError("#accept-conditions", "Debes aceptar las condiciones para votar");
            }

            if (this.errorFlag) {
                this.sendingFlag = false;
                $("#identify-action").removeAttr("disabled");
                return;
            }

            var inputData = {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "tlf": app_data.tlf,
                "postal_code": postal_code,
                "receive_updates": mail_updates,
                "dni": dni
            };

            var self = this;
            var jqxhr = $.ajax("/api/v1/register/", {
                data: JSON.stringify(inputData),
                contentType : 'application/json',
                type: 'POST',
            })
            .done(function(data) {
                self.sendingFlag = false;
                app.router.navigate("verify-sms", {trigger: true});
            })
            .fail(this.processError);
        },

        showErrorMessage: function(message, allow_try_again) {
            $("#error-message").html(message);
            if (allow_try_again) {
                $("#identify-action").removeAttr("disabled");
            }
        },

        processError: function(jqXHR, textStatus) {
            var self = app.current_view;
            self.sendingFlag = false;
            console.log("fail = " + jqXHR.responseText);
            try {
                var data = JSON.parse(jqXHR.responseText);
            } catch(e) {
                self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                'formulario. Por favor, ponte en <a href="#contact">contacto ' +
                'con nosotros</a> explicando en detalle los pasos que seguiste ' +
                'para que podamos reproducir y arreglar el problema.', false);
                return;
            }
            if (data.error_codename == "already_voted") {
                self.showErrorMessage('¡Vaya! Ya votaste anteriormente, no ' +
                'puedes votar dos veces.', false);
            } else if (data.error_codename == "blacklisted") {
                self.showErrorMessage('¡Vaya! Tu petición ha sido bloqueada. Puede ' +
                'que sea un error, o que alguien haya estado haciendo ' +
                'cosas raras. Si quieres puedes <a href="#contact">contactar ' +
                'con nosotros</a> para contarnos tu problema.', false);
            } else if (data.error_codename == "wait_hour") {
                self.showErrorMessage('¡Vaya! Has hecho demasiadas peticiones ' +
                'seguidas. Por seguridad, tendrás que esperar una hora para ' +
                'intentarlo de nuevo. Si quieres puedes ' +
                '<a href="#contact">contactar con nosotros</a> para contarnos ' +
                'tu problema.', false);
            } else if (data.error_codename == "wait_day") {
                self.showErrorMessage('¡Vaya! Has hecho demasiadas peticiones ' +
                'seguidas hoy. Por seguridad, se han bloqueado tus peticiones ' +
                'durante 24 horas. Si quieres puedes <a href="#contact">' +
                'contactar con nosotros</a> para contarnos tu problema.', false);
            } else if (data.error_codename == "wait_expire") {
                self.showErrorMessage('¡Ten paciencia! Te acabamos de enviar un SMS' +
                ' hace nada, espera a que te llegue y cuando te llegue ' +
                '<a href="#verify-sms">pincha aquí para ' +
                'verificar tu código SMS</a>.', false);
            } else {
                self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                'formulario. Por favor, ponte en <a href="#contact">contacto ' +
                'con nosotros</a> explicando en detalle los pasos que seguiste ' +
                'para que podamos reproducir y arreglar el problema.', false);
            }
        }
    });

    /**
     * Verify SMS view
     */
    AE.VerifySMSView = Backbone.View.extend({
        el: "#renderall",

        events: {
            'click #verify-action': 'processForm'
        },

        initialize: function() {
            this.template = _.template($("#template-verify-sms-view").html());
            this.render();
        },

        render: function() {
            if (!app_data.tlf) {
                app_data.tlf = null;
            }
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        },

        /**
         * Used in setError and processForm to detect errors
         */
        errorFlag: false,

        /**
         * detects when we are sending a petition
         */
        sendingFlag: false,

        /**
         *  Help function to set the
         */
        setError: function(selector, text) {
            this.errorFlag = true;
            $(selector).parent().find(".help-block").html(text);
            $(selector).closest(".form-group").addClass("has-error");
        },

        /**
         * Does the heavy duty stuff in this view, processes the form, showing
         * errors if any, or sending the data and showing the SMS code
         * verification form.
         */
        processForm: function(e) {
            if (this.sendingFlag) {
                return;
            }
            this.sendingFlag = true;
            // reset errors
            this.errorFlag = false;
            $("#verify-action").attr("disabled", "disabled");
            $(".form-group.has-error .help-block").each(function() {
                $(this).html("");
            });
            $(".form-group").removeClass("has-error");

            // get the data
            var tlf = null;
            if (app_data.tlf) {
                tlf = app_data.tlf;
            } else {
                tlf = $("#tlf").val();
            }
            var sms_code = $("#sms-code").val().trim().toUpperCase();

            // start checking
            if (sms_code.length != 8)
            {
                this.setError("#sms-code", "Código introducido inválido");
            }

            tlf = Checker.tlf(tlf)
            if (!tlf) {
                this.setError("#tlf", "Debes introducir un teléfono español válido. Ejemplo: 666 666 666");
            }

            if (this.errorFlag) {
                this.sendingFlag = false;
                $("#verify-action").removeAttr("disabled");
                return;
            }

            var inputData = {
                "tlf": tlf,
                "token": sms_code
            };

            var self = this;
            var jqxhr = $.ajax("/api/v1/sms_auth/", {
                data: JSON.stringify(inputData),
                contentType : 'application/json',
                type: 'POST',
            })
            .done(function(data) {
                try {
                    data = JSON.parse(data);
                } catch(e) {
                    self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                    'formulario. Por favor, ponte en <a href="#contact">contacto ' +
                    'con nosotros</a> explicando en detalle los pasos que seguiste ' +
                    'para que podamos reproducir y arreglar el problema.', false);
                    return;
                }
                var url = app_data.election.url + "/vote?message=" + encodeURIComponent(data.message) + "&sha1_hmac=" + encodeURIComponent(data.sha1_hmac);
                document.location.href=url;
            })
            .fail(this.processError);
        },

        showErrorMessage: function(message, allow_try_again) {
            $("#error-message").html(message);
            if (allow_try_again) {
                $("#verify-action").removeAttr("disabled");
            }
        },

        processError: function(jqXHR, textStatus) {
            var self = app.current_view;
            self.sendingFlag = false;
            console.log("fail = " + jqXHR.responseText);
            try {
                var data = JSON.parse(jqXHR.responseText);
            } catch(e) {
                self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                'formulario. Por favor, ponte en <a href="#contact">contacto ' +
                'con nosotros</a> explicando en detalle los pasos que seguiste ' +
                'para que podamos reproducir y arreglar el problema.', false);
                return;
            }
            if (data.error_codename == "already_voted") {
                self.showErrorMessage('¡Vaya! Ya votaste anteriormente, no ' +
                'puedes votar dos veces.', false);
            } else if (data.error_codename == "sms_notsent") {
                self.showErrorMessage('No tienes ningún mensaje SMS pendiente de verificar, debes ' +
                '<a href="#identify">identificarte</a> primero/de nuevo.', false);
            } else if (data.error_codename == "need_new_token") {
                self.showErrorMessage('¡Vaya! Se te han acabado el número ' +
                'de intentos para escribir el código SMS. Deberás ' +
                '<a href="#identify">identificarte</a> de nuevo.', false);
            } else if (data.error_codename == "invalid_token") {
                self.showErrorMessage('¡Vaya! El código SMS que has ' +
                    'introducido es incorrecto, por favor compruébalo.', true);
            } else {
                self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                'formulario. Por favor, ponte en <a href="#contact">contacto ' +
                'con nosotros</a> explicando en detalle los pasos que seguiste ' +
                'para que podamos reproducir y arreglar el problema.', false);
            }
        }
    });

    /**
     * Authorities list view
     */
    AE.AuthoritiesView = Backbone.View.extend({
        el: "#renderall",

        initialize: function() {
            this.template = _.template($("#template-authorities-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        }
    });

    /**
     * FAQ view
     */
    AE.FAQView = Backbone.View.extend({
        el: "#renderall",

        initialize: function() {
            this.template = _.template($("#template-faq-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        }
    });

    /**
     * Mail sent view
     */
    AE.MailSentView = Backbone.View.extend({
        el: "#renderall",

        initialize: function() {
            this.template = _.template($("#template-mail-sent-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        }
    });

    /**
     * Contact form view
     */
    AE.ContactView = Backbone.View.extend({
        el: "#renderall",

        events: {
            'click #send-message': 'processForm'
        },

        initialize: function() {
            this.template = _.template($("#template-contact-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        },

        /**
         * Used in setError and processForm to detect errors
         */
        errorFlag: false,

        /**
         * detects when we are sending a petition
         */
        sendingFlag: false,

        /**
         *  Help function to set the
         */
        setError: function(selector, text) {
            this.errorFlag = true;
            $(selector).parent().find(".help-block").html(text);
            $(selector).closest(".form-group").addClass("has-error");
        },

        /**
         * Does the heavy duty stuff in this view, processes the form, showing
         * errors if any, or sending the data and showing the SMS code
         * verification form.
         */
        processForm: function(e) {
            if (this.sendingFlag) {
                return;
            }
            this.sendingFlag = true;
            // reset errors
            this.errorFlag = false;
            $("#send-message").attr("disabled", "disabled");
            $(".form-group.has-error .help-block").each(function() {
                $(this).html("");
            });
            $(".form-group").removeClass("has-error");

            // get the data
            var name = $("#name").val().trim();
            var email = $("#email").val().trim();
            var tlf = $("#tlf").val().trim();
            var text_body = $("#text-body").val().trim();

            // start checking
            if (name.length < 3 || name.length >= 60)
            {
                this.setError("#name", "Obligatorio, de 3 a 60 caracteres");
            }

            if (email.length < 3 || email.length >= 140 ||
                    !Checker.email(email))
            {
                this.setError("#email", "Debes introducir una dirección email válida");
            }

            if (tlf.length > 0) {
                tlf = Checker.tlf(tlf);
                if (!tlf) {
                    this.setError("#tlf", "Introduce un número de teléfono válido, por ejemplo: 666 666 666");
                }
            }

            if (name.length < 5 || name.length >= 160)
            {
                this.setError("#name", "Obligatorio, de 5 a 160 caracteres");
            }

            if (text_body.length < 10 || text_body.length >= 4000)
            {
                this.setError("#text-body", "Obligatorio, de 10 a 4000 caracteres");
            }

            if (this.errorFlag) {
                this.sendingFlag = true;
                $("#send-message").removeAttr("disabled");
                return;
            }

            var inputData = {
                "name": name,
                "email": email,
                "tlf": tlf,
                "body": text_body
            };

            var self = this;
            var jqxhr = $.ajax("/api/v1/contact/", {
                data: JSON.stringify(inputData),
                contentType : 'application/json',
                type: 'POST',
            })
            .done(function(data) {
                console.log(data);
                self.sendingFlag = false;
                app.router.navigate("mail-sent", {trigger: true});
            })
            .fail(this.processError);
        },

        showErrorMessage: function(message, allow_try_again) {
            $("#error-message").html(message);
            if (allow_try_again) {
                $("#send-message").removeAttr("disabled");
            }
        },

        processError: function(jqXHR, textStatus) {
            var self = app.current_view;
            self.sendingFlag = false;
            console.log("fail = " + jqXHR.responseText);
            try {
                var data = JSON.parse(jqXHR.responseText);
            } catch(e) {
                self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
                'formulario. Por favor, ponte en contacto con nosotros ' +
                'enviandonos un email o por twitter.', false);
                return;
            }
            self.showErrorMessage('Ha ocurrido un error interno enviando el ' +
            'formulario. Por favor, ponte en contacto con nosotros ' +
            'enviandonos un email o por twitter.', false);
        }
    });

    /**
     * Modal dialog, reusable
     */
    AE.ModalDialogView = Backbone.View.extend({
        el: "#show-modal",

        initialize: function() {
            this.template = _.template($("#template-modal-dialog-view").html());
        },

        render: function(title, body, footer) {
            var obj = {
                title: title,
                body: body,
                footer: footer
            };
            this.$el.html(this.template(obj));
            this.delegateEvents();
            this.$el.find("#modal-dialog").modal('show');
            return this;
        }
    });

    /**
     * Security Center view
     */
    AE.SecurityCenterView = Backbone.View.extend({
        el: "#renderall",
        class_name: "security-center",

        events: {
            'click #verify-action': 'processForm'
        },

        initialize: function() {
            this.template = _.template($("#template-security-center-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            var hash = window.location.hash;
            $('#verify-tabs a[href="' + hash + '"]').tab('show');
            this.delegateEvents();
            return this;
        },

        /**
         * Used in setError and processForm to detect errors
         */
        errorFlag: false,

        /**
         * detects when we are sending a petition
         */
        sendingFlag: false,

        /**
         *  Help function to set the
         */
        setError: function(selector, text) {
            this.errorFlag = true;
            $(selector).parent().find(".help-block").html(text);
            $(selector).closest(".form-group").addClass("has-error");
        },

        showErrorMessage: function(message, allow_try_again) {
            $("#error-message").html(message);
            if (allow_try_again) {
                $("#verify-action").removeAttr("disabled");
            }
        },

        /**
         * Locate the tracker id and see if it exists
         */
        processForm: function() {
            if (this.sendingFlag) {
                return;
            }
            this.sendingFlag = true;
            // reset errors
            this.errorFlag = false;
            $("#verify-action").attr("disabled", "disabled");
            $("#error-message").empty();
            $("#verify-result").addClass("hidden");
            $(".form-group.has-error .help-block").each(function() {
                $(this).empty();
            });
            $(".form-group").removeClass("has-error");

            var tracker = $("#tracker").val().toLowerCase();
            if (!/[0-9a-f]{64}/.test(tracker)) {
                this.setError("#tracker", "El tracker que has introducido " +
                              "es incorrecto");
            }

            if (this.errorFlag) {
                $("#verify-action").removeAttr("disabled");
                this.sendingFlag = false;
                return;
            }

            $("#tracker-id").html(tracker);

            var e_id = app_data.election.id;
            var base_url = app_data.election.base_url;
            var url = base_url + "/api/v1/election/" + e_id +
                      "/all_votes/?limit=1&offset=0&" +
                      "username=" + encodeURIComponent(tracker);

            var self = this;
            var jqxhr = $.ajax(url, {
                contentType: 'application/json'
            }).done(this.processSuccess)
            .fail(this.processError);
        },

        processSuccess: function(data) {
            app.current_view.sendingFlag = false;
            $("#verify-action").removeAttr("disabled");
            if (data.objects.length == 0) {
                app.current_view.showErrorMessage('No hemos encontrado el tracker ' +
                'que has introducido ¿seguro que es correcto?', true);
                return;
            }
            var vote = JSON.stringify(data.objects[0].public_data);
            $("#vote-details").html(vote);
            $("#verify-result").removeClass("hidden");
        },

        processError: function(jqXHR, textStatus) {
            app.current_view.sendingFlag = false;
            $("#verify-action").removeAttr("disabled");
            app.current_view.showErrorMessage('Ha ocurrido un error interno ' +
            'enviando el formulario. Por favor, ponte en <a ' +
            'href="#contact">contacto con nosotros</a> explicando ' +
            'en detalle los pasos que seguiste para que podamos ' +
            'reproducir y arreglar el problema.', true);
            return;
        }
    });

    main();
}).call(this);
