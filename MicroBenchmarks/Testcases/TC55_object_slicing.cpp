// Category: Object-Oriented Errors
// Error: Slicing in inheritance

#include <iostream>

class Base {
public:
    virtual void print() {
        std::cout << "Base class" << std::endl;
    }
    int baseValue = 10;
};

class Derived : public Base {
public:
    void print() override {
        std::cout << "Derived class with extra: " << extraValue << std::endl;
    }
    int extraValue = 20;
};

void processObject(Base obj) {  // ERROR: Pass by value causes slicing
    obj.print();  // Will call Base::print, not Derived::print
}

int main() {
    Derived d;
    processObject(d);  // Slicing occurs here
    
    return 0;
}
