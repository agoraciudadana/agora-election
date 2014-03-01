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

    /*
     * main view, that routers everything
     */
    var AE = this.AE = {}; // AE  means "Agora Election"
    var app = this.app = {};
    app.current_view = null;

    var main = function() {
        // Initiate the router
        app.router = new AE.Router();

        // Start Backbone history a necessary step for bookmarkable URL's
        Backbone.history.start();
    };

    AE.Router = Backbone.Router.extend({
        routes: {
            "": "home",
            "identify": "identify"
        },

        home: function() {
            console.log("home!");
            app.current_view = new AE.HomeView();
        },

        identify: function(actions) {
            console.log("identify!");
            app.current_view = new AE.IdentityView();
        }
    });

    AE.ElectionModel = Backbone.Model.extend({});

    AE.HomeView = Backbone.View.extend({
        el: "#renderall",

        initialize: function() {
            this.template = _.template($("#template-home-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        }
    });

    AE.IdentityView = Backbone.View.extend({
        el: "#renderall",

        initialize: function() {
            this.template = _.template($("#template-identify-view").html());
            this.render();
        },

        render: function() {
            this.$el.html(this.template(app_data));
            this.delegateEvents();
            return this;
        }
    });


    main();
}).call(this);
